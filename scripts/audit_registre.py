#!/usr/bin/env python3
"""Registre des audits : statuts CALCULES (AMET91, METHODE v3 §C.4, §D.5).

    python scripts/audit_registre.py status          # tableau (lecture seule)
    python scripts/audit_registre.py --du            # groupes dont le `verifie` est du
    python scripts/audit_registre.py claim <id>      # branche audit-<id> + commit vide
    python scripts/audit_registre.py prochain-id <G> # max + 1 sur tous les plans
    python scripts/audit_registre.py --check         # registre <-> dossiers <-> plans

Statuts, du plus bas au plus haut (jamais lus dans `unites.yml`, jamais reecrits) :
  a auditer   pas de dossier (`dossier:` absent ou fichier manquant)
  en cours    pas de dossier mais une branche de claim vivante
  audite      dossier present
  construit   >= 95 % des taches constructibles du groupe cochees (tous plans +
              ledger de docs/done_task.md ; [BLOCKED], [SKIP], (GATED) exclues)
  accepte     construit + `check_acceptation.py --groupe <G>` code 0 ("n/d" tant
              que cette garde n'existe pas)
  verifie     construit + dernier `docs/audits/*-<mot>-verifie.md` sans ecart S1-S2
              (marqueur optionnel `<!-- verifie | groupe: G | pct: N |
              ecarts_s1_s2: N -->` ; a defaut, tout `S1`/`S2` du fichier compte).

`unites.yml` n'est JAMAIS reecrit : son champ `statut` reste informatif.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_taches_cablage as ctc  # noqa: E402
from plan_lanes import _MiniYamlParser  # noqa: E402

ROOT = HERE.parent
UNITES = "docs/audits/unites.yml"
DECISIONS = "docs/audits/decisions.yml"
DONE_TASK = "docs/done_task.md"
SEUIL_CONSTRUIT = 95
SEUIL_MI_PARCOURS = 50
PERIME_HEURES = 48
_LEDGER = re.compile(r"^([A-Z]+(?:-[A-Z]+)?)=(\d+)$")
_MARQUEUR = re.compile(r"<!--\s*verifie\b(?P<corps>.*?)-->", re.S)
_ECART = re.compile(r"\bS[12]\b")


def _yaml(rel: str) -> dict:
    chemin = ROOT / rel
    if not chemin.is_file():
        return {}
    return _MiniYamlParser(chemin.read_text(encoding="utf-8")).parse()


def charger_unites() -> list:
    return list(_yaml(UNITES).get("unites") or [])


def _ledger() -> dict:
    chemin = ROOT / DONE_TASK
    comptes: dict = {}
    if not chemin.is_file():
        return comptes
    dedans = False
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not dedans:
            dedans = ligne.startswith("<!-- plan-progress-ledger")
            continue
        if ligne == "-->":
            break
        m = _LEDGER.match(ligne)
        if m:
            comptes[m.group(1)] = comptes.get(m.group(1), 0) + int(m.group(2))
    return comptes


def comptes(groupe: str, toutes: list, ledger: dict) -> tuple:
    """(cochees, constructibles) pour un prefixe : plans + ledger d'archive."""
    motif = re.compile(rf"^{re.escape(groupe)}\d+")
    cochees = ledger.get(groupe, 0)
    constructibles = cochees
    for t in toutes:
        if not motif.match(t.identifiant):
            continue
        etat = t.etat.strip()
        if etat.lower() == "x":
            cochees += 1
            constructibles += 1
        elif etat.upper().startswith(("BLOCKED", "SKIP")):
            continue
        elif re.search(r"\(GATED\b", t.texte):
            continue
        else:
            constructibles += 1
    return cochees, constructibles


def derniere_verifie(mot: str, groupe: str):
    """Dernier dossier `<date>-<mot>-verifie.md` : {fichier, date, pct, ecarts} ou None."""
    candidats = sorted((ROOT / "docs" / "audits").glob(f"*-{mot}-verifie.md"))
    if not candidats:
        return None
    chemin = candidats[-1]
    texte = chemin.read_text(encoding="utf-8", errors="replace")
    pct = None
    ecarts = None
    m = _MARQUEUR.search(texte)
    if m:
        corps = m.group("corps")
        p = re.search(r"pct:\s*(\d+)", corps)
        e = re.search(r"ecarts_s1_s2:\s*(\d+)", corps)
        pct = int(p.group(1)) if p else None
        ecarts = int(e.group(1)) if e else None
    if ecarts is None:
        ecarts = len(_ECART.findall(texte))
    return {"fichier": chemin.name, "date": chemin.name[:10], "pct": pct,
            "ecarts": ecarts}


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def claims_vivants(remote: str = "origin") -> dict:
    """{id: (age_heures)} des branches remote-tracking audit-* non fusionnees dans main."""
    sortie = _git("for-each-ref", f"--no-merged={remote}/main",
                  "--format=%(refname:short) %(committerdate:unix)",
                  f"refs/remotes/{remote}/audit-*")
    vivants = {}
    for ligne in sortie.stdout.splitlines():
        nom, _, quand = ligne.rpartition(" ")
        try:
            age = (time.time() - int(quand)) / 3600
        except ValueError:
            age = 0
        vivants[nom.split("/", 1)[-1][len("audit-"):]] = age
    return vivants


def acceptation(groupe: str) -> str:
    garde = ROOT / "scripts" / "check_acceptation.py"
    if not garde.is_file():
        return "n/d"
    try:
        r = subprocess.run([sys.executable, str(garde), "--groupe", groupe],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return "n/d"
    return {0: "oui", 1: "non"}.get(r.returncode, "n/d")


def calculer() -> list:
    toutes = ctc.lire_taches()
    ledger = _ledger()
    vivants = claims_vivants()
    lignes = []
    for u in sorted(charger_unites(), key=lambda x: x.get("rang", 999)):
        groupe = u.get("groupe") or ""
        dossier = str(u.get("dossier") or "")
        a_dossier = bool(dossier) and dossier != "null" and (ROOT / dossier).is_file()
        faits, total = comptes(groupe, toutes, ledger) if groupe else (0, 0)
        pct = int(100 * faits / total) if total else 0
        verifie = derniere_verifie(str(u.get("declencheur") or ""), groupe)
        accept = acceptation(groupe) if groupe and a_dossier else "n/d"
        if not a_dossier:
            statut = "en cours" if str(u.get("id")) in vivants else "à auditer"
        else:
            statut = "audité"
            if total and 100 * faits >= SEUIL_CONSTRUIT * total:
                statut = "construit"
                if accept == "oui":
                    statut = "accepté"
                if verifie and verifie["ecarts"] == 0:
                    statut = "vérifié"
        age = vivants.get(str(u.get("id")))
        lignes.append({
            "rang": u.get("rang"), "id": str(u.get("id")),
            "mot": str(u.get("declencheur") or ""), "groupe": groupe,
            "statut": statut, "faits": faits, "total": total, "pct": pct,
            "acceptation": accept, "verifie": verifie,
            "claim": None if age is None else
            f"audit-{u.get('id')} " + ("PÉRIMÉ " if age > PERIME_HEURES else "")
            + f"({age:.0f} h)",
        })
    return lignes


def cmd_status() -> int:
    entete = ("rang", "id", "mot", "statut", "% cochées", "acceptation",
              "dernier vérifie", "claim")
    rangs = [entete]
    for u in calculer():
        v = u["verifie"]
        rangs.append((
            str(u["rang"]), u["id"], u["mot"], u["statut"],
            f"{u['faits']}/{u['total']} ({u['pct']} %)" if u["total"] else "-",
            u["acceptation"],
            "-" if not v else f"{v['date']} ({v['ecarts']} écart S1-S2)",
            u["claim"] or "-"))
    largeurs = [max(len(r[i]) for r in rangs) for i in range(len(entete))]
    for r in rangs:
        print(" | ".join(c.ljust(largeurs[i]) for i, c in enumerate(r)).rstrip())
    return 0


def cmd_du() -> int:
    dus = []
    for u in calculer():
        if not u["groupe"] or not u["total"]:
            continue
        v = u["verifie"]
        if u["pct"] >= SEUIL_CONSTRUIT and not (v and (v["pct"] or 0) >= SEUIL_CONSTRUIT):
            seuil = f"clôture (≥ {SEUIL_CONSTRUIT} %), pas vérifié depuis"
        elif u["pct"] >= SEUIL_MI_PARCOURS and not v:
            seuil = f"mi-parcours (≥ {SEUIL_MI_PARCOURS} %), jamais vérifié"
        else:
            continue
        dus.append(f"{u['groupe']} ({u['id']} {u['mot']}) : {u['pct']} % cochées "
                   f"({u['faits']}/{u['total']}) — vérifie dû, {seuil}")
    print(f"Vérifie dû : {len(dus)} groupe(s)")
    for ligne in dus:
        print(f"  {ligne}")
    ouvertes = [str(d.get("id")) for d in _yaml(DECISIONS).get("decisions") or []
                if str(d.get("reponse")) == "ouverte"]
    print(f"Décisions ouvertes : {len(ouvertes)}"
          + (f" ({', '.join(ouvertes)})" if ouvertes else ""))
    print("Dette d'acceptation : "
          + ("n/d (scripts/check_acceptation.py absent)"
             if not (ROOT / "scripts" / "check_acceptation.py").is_file()
             else "voir `python scripts/check_acceptation.py`"))
    return 0


def cmd_prochain_id(groupe: str) -> int:
    motif = re.compile(rf"\b{re.escape(groupe)}(\d+)(?:\s*[–-]\s*(?:{re.escape(groupe)})?(\d+))?")
    maxi = 0
    for t in ctc.lire_taches():
        m = re.match(rf"^{re.escape(groupe)}(\d+)$", t.identifiant)
        if m:
            maxi = max(maxi, int(m.group(1)))
    archive = ROOT / DONE_TASK
    if archive.is_file():
        for m in motif.finditer(archive.read_text(encoding="utf-8")):
            maxi = max(maxi, int(m.group(1)), int(m.group(2) or 0))
    print(f"{groupe}{maxi + 1}")
    return 0


def cmd_claim(identifiant: str, remote: str = "origin") -> int:
    if identifiant not in {str(u.get("id")) for u in charger_unites()}:
        print(f"Unité inconnue : {identifiant} (absente de {UNITES}).")
        return 2
    branche = f"audit-{identifiant}"
    deja = _git("ls-remote", "--heads", remote, branche)
    if deja.returncode == 0 and deja.stdout.strip():
        print(f"Refus : {branche} existe déjà sur {remote} — unité prise.")
        return 1
    if _git("fetch", remote, "main").returncode != 0:
        print(f"Échec : git fetch {remote} main.")
        return 2
    base = f"{remote}/main"
    arbre = _git("rev-parse", f"{base}^{{tree}}").stdout.strip()
    parent = _git("rev-parse", base).stdout.strip()
    env_id = [] if _git("config", "user.name").stdout.strip() else \
        ["-c", "user.name=audit-registre", "-c", "user.email=audit@taqinor.local"]
    commit = _git(*env_id, "commit-tree", arbre, "-p", parent, "-m",
                  f"claim {branche}")
    if commit.returncode != 0:
        print(f"Échec : commit vide impossible — {commit.stderr.strip()}")
        return 2
    sha = commit.stdout.strip()
    pousse = _git("push", remote, f"{sha}:refs/heads/{branche}")
    if pousse.returncode != 0:
        print(f"Refus : push de {branche} rejeté — unité prise ailleurs.")
        return 1
    _git("branch", branche, sha)
    print(f"Claim {branche} posé ({sha[:9]}) sur {remote}.")
    return 0


def cmd_check() -> int:
    erreurs = []
    ids_groupes = {re.sub(r"\d+$", "", i) for i in
                   (t.identifiant for t in ctc.lire_taches())} | set(_ledger())
    for u in charger_unites():
        uid = u.get("id")
        for champ in ("dossier", "plan"):
            valeur = str(u.get(champ) or "")
            if valeur and valeur != "null" and not (ROOT / valeur).is_file():
                erreurs.append(f"{uid} : `{champ}` {valeur} introuvable.")
        for rel in u.get("plans_alimentes") or []:
            if not (ROOT / str(rel)).is_file():
                erreurs.append(f"{uid} : plans_alimentes {rel} introuvable.")
        groupe = u.get("groupe")
        if groupe and groupe not in ids_groupes:
            erreurs.append(f"{uid} : groupe {groupe} ne correspond à aucune "
                           "tâche d'aucun plan.")
    for e in erreurs:
        print(f"ERREUR registre : {e}")
    if not erreurs:
        print("Registre des audits : unites.yml cohérent avec dossiers et plans.")
    return 1 if erreurs else 0


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")
    a = list(sys.argv[1:] if argv is None else argv)
    if a[:1] == ["status"]:
        return cmd_status()
    if a[:1] == ["--du"]:
        return cmd_du()
    if a[:1] == ["--check"]:
        return cmd_check()
    if a[:1] == ["claim"] and len(a) == 2:
        return cmd_claim(a[1])
    if a[:1] == ["prochain-id"] and len(a) == 2:
        return cmd_prochain_id(a[1])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
