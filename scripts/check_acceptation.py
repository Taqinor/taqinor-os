"""Garde d'acceptation (AMET88, constat C-AMET-020) — sans état, job stage-names.

Toute tâche cochée à preuve exécutable d'un groupe d'audit est couverte par un
enregistrement PASS, ou figure dans la dette gelée de son groupe, qui ne fait que
rétrécir. Pourquoi : 0/19 acceptations jouées, groupes mergés 1-18 fois sous CI
verte avec 2 régressions d'écran (ATOT2, ATOT9) — l'acceptation était une tâche
ordinaire confiée à des lanes sans pile (CLAUDE.md étape 3-bis, METHODE §C.4).

TÂCHES À COUVRIR — ligne `- [x] <ID> — …` d'un `docs/plans/PLAN_AUDIT_*.md` (lue
par `check_taches_cablage.lire_taches`) qui porte le tag `(@acceptation)`, ou un
titre « Acceptation live … », ou dont la clause « Preuve en direct : … » cite une
étape `P<n>[.<m>]` ou de parcours `PA<n>` (« n/a — … » et « API seulement — … »
ne comptent jamais). Groupe <G> = préfixe alphabétique de l'id (ADEP16 → ADEP).

CONTRAT PARTAGÉ — un enregistrement (écrit à la main par l'orchestrateur, ou par
la spec Playwright d'AMET90) = deux fichiers frères :
  docs/audits/acceptation/<G>/<AAAA-MM-JJ>-<sha9>.md            vue humaine
  docs/audits/acceptation/<G>/<AAAA-MM-JJ>-<sha9>.results.json  FAIT FOI
<G> = groupe porteur, <sha9> = 9 premiers caractères du sha rejoué. Le .md
s'ouvre sur un en-tête YAML lisible par `plan_lanes._MiniYamlParser` (listes en
flux `[a, b]`, mappings en bloc, jamais de `{…}` ni de `#` dans une valeur) :
  ---
  sha: <sha complet, 9 à 40 hex>
  date: AAAA-MM-JJ
  groupe: <G>
  couvre: [ADEP16, ADEP17]
  couvre_avec_ecart: []
  verdict: PASS
  etapes:
    - id: P1.1
      tache: [ADEP16]
      verdict: PASS
  ---
results.json = {"sha", "date", "groupe", "verdict": "PASS"|"FAIL", "couvre": [ids],
"couvre_avec_ecart": [ids], "etapes": [{"id": "P1.1", "taches": ["ADEP16"],
"verdict": "PASS"|"FAIL", "base_verdict": "PASS"|"FAIL"|null, "trace": "<chemin>",
"oracles": {"1": "PASS"|"FAIL"|"NA", …, "10": …}}]} — oracles = qa-explorer 1-10.
Règles : nom == date + sha[:9], dossier == groupe ; en-tête == results.json (sha,
date, groupe, verdict, couvre, couvre_avec_ecart, ids d'étapes) ; chaque étape a
id, ≥ 1 tâche, verdict, les 10 oracles et une trace (sinon « étape vide ») ; une
étape PASS n'a aucun oracle FAIL ; chaque id de `couvre` a ≥ 1 étape ;
couvre_avec_ecart ⊆ couvre ; dans un enregistrement PASS, une étape FAIL n'est
admise que si toutes ses tâches sont dans couvre_avec_ecart ET `base_verdict:
FAIL` (la même étape rejouée sur la base échoue aussi : défaut préexistant, pas
une régression). Seul un PASS couvre (un FAIL reste une trace) ; un rejeu de
parcours couvre des ids de tout groupe. Les dossiers dont le nom n'est pas un
groupe (ex. la capture brute `2026-10-07-adoc171/`) sont ignorés.

DETTE — docs/audits/acceptation/<G>/_dette.yml (clé = id de tâche, jamais une
ligne) : `groupe: <G>`, `amorce: <sha9>`, `ids:` en liste de blocs. Amorcée UNE
fois par `--amorcer` (à la bascule = l'arrivée de cette garde) ; ne fait que
rétrécir : un id absent du même fichier à la base git (`--base`, défaut
origin/main ; en CI à historique court la base est récupérée par un fetch
superficiel, sinon la comparaison est sautée avec un avis) ⇒ ÉCHEC ; un
`_dette.yml` absent de la base n'est admis que si la base n'a encore AUCUNE
dette (la bascule) ; un id couvert ou plus coché à preuve ⇒ ÉCHEC jusqu'à
`--write-baseline` (la mécanique de cliquet de taches_cablage_allow.txt).

Usage :
  python scripts/check_acceptation.py [--base REF]   # garde (exit 1 si rouge)
  python scripts/check_acceptation.py --rapport      # mêmes lignes, exit 0
  python scripts/check_acceptation.py --amorcer      # amorce les dettes absentes
  python scripts/check_acceptation.py --write-baseline  # rétrécit les dettes
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_taches_cablage as ctc  # noqa: E402
import plan_lanes  # noqa: E402

DOSSIER = "docs/audits/acceptation"
VERDICTS = ("PASS", "FAIL")
ORACLES = tuple(str(i) for i in range(1, 11))
_PREUVE = re.compile(r"Preuve en direct\s*:\s*(?P<v>.*?)"
                     r"(?=Hors p[ée]rim[èe]tre\s*:|\(gen\b|\bFiles?\s*:|$)", re.I)
_SANS_PREUVE = re.compile(r"\s*(?:n/a|API seulement)", re.I)
_ETAPE = re.compile(r"\bPA?\d")
# Tag NU seulement (un `(@acceptation)` cité entre backticks dans une tâche qui en PARLE ne
# compte pas) : lecteur unique `plan_lanes._AT_ACCEPTATION_RE` (AMET89).
_TAG = re.compile(plan_lanes._AT_ACCEPTATION_RE.pattern
                  + r"|^\S+\s+—\s+\**\s*Acceptation live", re.I)
_GROUPE = re.compile(r"[A-Z]+")
_NOM = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})-(?P<sha>[0-9a-f]{9})\.md")
_NOM_GROUPE = re.compile(r"[A-Z][A-Z0-9]*")
ENTETE_DETTE = (
    "# Dette d'acceptation GELÉE du groupe {g} (AMET88, scripts/check_acceptation.py).\n"
    "# Clé = id de tâche cochée à preuve en direct, ni couverte par un enregistrement\n"
    "# PASS. Elle ne fait que RÉTRÉCIR : `--write-baseline` retire les ids couverts ;\n"
    "# tout ajout fait échouer la garde. Amorcée à la bascule (sha ci-dessous).\n")


def groupe_de(ident: str) -> str:
    m = _GROUPE.match(ident)
    return m.group(0) if m else ident


def _cle(ident: str):
    m = re.match(r"([A-Za-z]+)(\d+)", ident)
    return (m.group(1), int(m.group(2)), ident) if m else (ident, 0, ident)


def _liste(valeur) -> list:
    if valeur in (None, ""):
        return []
    if isinstance(valeur, list):
        return [str(v) for v in valeur if v not in (None, "")]
    return [str(valeur)]


def _rel(chemin) -> str:
    try:
        return Path(chemin).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(chemin)


def a_preuve(texte: str) -> bool:
    if _TAG.search(texte):
        return True
    return any(not _SANS_PREUVE.match(m.group("v")) and _ETAPE.search(m.group("v"))
               for m in _PREUVE.finditer(texte))


def taches_a_preuve() -> dict:
    """{id: Tache} des tâches cochées à preuve exécutable des PLAN_AUDIT_*.md."""
    plans = sorted((ROOT / "docs" / "plans").glob("PLAN_AUDIT_*.md"))
    trouvees = {}
    for tache in ctc.lire_taches([str(p) for p in plans]):
        if tache.close and a_preuve(tache.texte):
            trouvees.setdefault(tache.identifiant, tache)
    return trouvees


def _en_tete(texte: str):
    lignes = texte.splitlines()
    if not lignes or lignes[0].strip() != "---":
        return None
    for i, ligne in enumerate(lignes[1:], 1):
        if ligne.strip() == "---":
            return plan_lanes._MiniYamlParser("\n".join(lignes[1:i])).parse()
    return None


def _etape_complete(e) -> bool:
    oracles = e.get("oracles") if isinstance(e.get("oracles"), dict) else {}
    return bool(e.get("id") and _liste(e.get("taches", e.get("tache")))
                and e.get("verdict") in VERDICTS and e.get("trace")
                and sorted(oracles) == sorted(ORACLES)
                and all(v in ("PASS", "FAIL", "NA") for v in oracles.values()))


def _charger_enregistrement(md: Path, err):
    """(results, en-tête) d'un enregistrement, ou None (erreur déjà signalée)."""
    rj = md.with_name(md.name[:-3] + ".results.json")
    if not rj.is_file():
        err(f"{rj.name} : results.json absent (il fait foi)")
        return None
    try:
        res = json.loads(rj.read_text(encoding="utf-8"))
        tete = _en_tete(md.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        err(f"illisible ({exc})")
        return None
    if not isinstance(res, dict) or not isinstance(tete, dict):
        err("en-tête YAML `---` ou objet results.json manquant")
        return None
    return res, tete


def _verifier_identite(res: dict, nom, md: Path, err):
    sha, verdict = str(res.get("sha") or ""), res.get("verdict")
    if not re.fullmatch(r"[0-9a-f]{9,40}", sha) or sha[:9] != nom["sha"]:
        err(f"sha « {sha} » ≠ nom de fichier ({nom['sha']})")
    if str(res.get("date")) != nom["date"]:
        err(f"date « {res.get('date')} » ≠ nom de fichier ({nom['date']})")
    if res.get("groupe") != md.parent.name:
        err(f"groupe « {res.get('groupe')} » ≠ dossier {md.parent.name}")
    if verdict not in VERDICTS:
        err(f"verdict « {verdict} » (attendu PASS ou FAIL)")


def _verifier_couvre(couvre: set, ecart: set, err):
    if not couvre:
        err("`couvre` vide")
    if ecart - couvre:
        err(f"couvre_avec_ecart hors de couvre : {', '.join(sorted(ecart - couvre))}")


def _verifier_etape(n: int, e, verdict, ecart: set, err):
    """Tâches de l'étape `e` (set), ou None si elle est vide/incomplète."""
    if not isinstance(e, dict) or not _etape_complete(e):
        err(f"étape {n} vide ou incomplète (id, taches, verdict, oracles 1-10 "
            "PASS/FAIL/NA, trace)")
        return None
    taches = set(_liste(e.get("taches", e.get("tache"))))
    if e["verdict"] == "PASS" and "FAIL" in e["oracles"].values():
        err(f"étape {e['id']} PASS avec un oracle FAIL")
    if e["verdict"] == "FAIL" and verdict == "PASS" and not (
            taches <= ecart and e.get("base_verdict") == "FAIL"):
        err(f"étape {e['id']} FAIL dans un enregistrement PASS : seul un écart "
            "accepté (couvre_avec_ecart) qui échoue aussi à la base "
            "(base_verdict: FAIL) est admis")
    return taches


def _verifier_etapes(etapes: list, verdict, ecart: set, err) -> set:
    """Contrôle chaque étape ; renvoie l'union des tâches vues."""
    if not etapes:
        err("aucune étape")
    vues = set()
    for n, e in enumerate(etapes, 1):
        vues |= _verifier_etape(n, e, verdict, ecart, err) or set()
    return vues


def _verifier_entete(tete: dict, res: dict, couvre: set, ecart: set, err):
    """L'en-tête YAML du .md doit refléter results.json (qui fait foi)."""
    for cle in ("sha", "date", "groupe", "verdict"):
        if str(tete.get(cle)) != str(res.get(cle)):
            err(f"en-tête `{cle}` ≠ results.json")
    if set(_liste(tete.get("couvre"))) != couvre:
        err("en-tête `couvre` ≠ results.json")
    if set(_liste(tete.get("couvre_avec_ecart"))) != ecart:
        err("en-tête `couvre_avec_ecart` ≠ results.json")
    etapes = res.get("etapes") if isinstance(res.get("etapes"), list) else []
    ids_tete = {str(x.get("id")) for x in tete.get("etapes") or [] if isinstance(x, dict)}
    if ids_tete != {str(e.get("id")) for e in etapes if isinstance(e, dict)}:
        err("en-tête `etapes` ≠ étapes de results.json")


def lire_enregistrement(md: Path, erreurs: list):
    """Ids couverts par un enregistrement conforme (vide si FAIL), None si non conforme."""
    nb_avant = len(erreurs)

    def err(msg):
        erreurs.append(f"{_rel(md)} : {msg}")

    nom = _NOM.fullmatch(md.name)
    if not nom:
        err("nom non conforme (attendu <AAAA-MM-JJ>-<sha9>.md)")
        return None
    charge = _charger_enregistrement(md, err)
    if charge is None:
        return None
    res, tete = charge
    verdict = res.get("verdict")
    _verifier_identite(res, nom, md, err)
    couvre = set(_liste(res.get("couvre")))
    ecart = set(_liste(res.get("couvre_avec_ecart")))
    _verifier_couvre(couvre, ecart, err)
    etapes = res.get("etapes") if isinstance(res.get("etapes"), list) else []
    vues = _verifier_etapes(etapes, verdict, ecart, err)
    if couvre - vues:
        err(f"ids de `couvre` sans étape : {', '.join(sorted(couvre - vues, key=_cle))}")
    _verifier_entete(tete, res, couvre, ecart, err)
    if len(erreurs) > nb_avant:
        return None
    return couvre if verdict == "PASS" else set()


def _dossiers_groupes() -> list:
    racine = ROOT / DOSSIER
    if not racine.is_dir():
        return []
    return sorted(p for p in racine.iterdir()
                  if p.is_dir() and _NOM_GROUPE.fullmatch(p.name))


def enregistrements(erreurs: list) -> set:
    couverts = set()
    for dossier in _dossiers_groupes():
        for md in sorted(dossier.glob("*.md")):
            couverts |= lire_enregistrement(md, erreurs) or set()
        for rj in sorted(dossier.glob("*.results.json")):
            if not rj.with_name(rj.name[:-len(".results.json")] + ".md").is_file():
                erreurs.append(f"{_rel(rj)} : results.json sans son enregistrement .md")
    return couverts


def _ids_dette(texte: str) -> set:
    return set(_liste(plan_lanes._MiniYamlParser(texte).parse().get("ids")))


def dettes() -> dict:
    return {d.name: _ids_dette((d / "_dette.yml").read_text(encoding="utf-8"))
            for d in _dossiers_groupes() if (d / "_dette.yml").is_file()}


def ecrire_dette(groupe: str, ids: set, amorce: str):
    chemin = ROOT / DOSSIER / groupe / "_dette.yml"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    corps = "".join(f"  - {i}\n" for i in sorted(ids, key=_cle)) if ids else ""
    chemin.write_text(ENTETE_DETTE.format(g=groupe) + f"groupe: {groupe}\n"
                      f"amorce: {amorce}\nids:{'' if ids else ' []'}\n{corps}",
                      encoding="utf-8", newline="\n")


def _git(*args, timeout=60):
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def base_disponible(base: str) -> bool:
    if _git("rev-parse", "--verify", "--quiet", base + "^{commit}") is not None:
        return True
    if os.environ.get("GITHUB_ACTIONS") and base == "origin/main":
        _git("fetch", "--no-tags", "--depth=1", "origin",
             "+refs/heads/main:refs/remotes/origin/main", timeout=120)
        return _git("rev-parse", "--verify", "--quiet", base + "^{commit}") is not None
    return False


def croissances(base: str, actuelles: dict) -> list:
    noms = (_git("ls-tree", "-r", "--name-only", base, "--", DOSSIER) or "").splitlines()
    a_la_base = {n.strip() for n in noms if n.strip().endswith("/_dette.yml")}
    erreurs = []
    for groupe, ids in sorted(actuelles.items()):
        rel = f"{DOSSIER}/{groupe}/_dette.yml"
        if rel in a_la_base:
            neufs = ids - _ids_dette(_git("show", f"{base}:{rel}") or "")
        else:
            neufs = ids if a_la_base else set()
        if neufs:
            erreurs.append(f"dette {groupe} : a GROSSI par rapport à {base} "
                           f"(+{', '.join(sorted(neufs, key=_cle))}) — la dette ne fait "
                           "que rétrécir : jouez l'acceptation (CLAUDE.md 3-bis)")
    return erreurs


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Garde d'acceptation (AMET88).")
    ap.add_argument("--base", default="origin/main",
                    help="ref git de comparaison de la dette (défaut origin/main)")
    ap.add_argument("--rapport", action="store_true", help="affiche seulement (exit 0)")
    ap.add_argument("--amorcer", action="store_true",
                    help="amorce UNE fois la dette des groupes qui n'en ont pas")
    ap.add_argument("--write-baseline", action="store_true",
                    help="retire de la dette les ids couverts ou plus cochés à preuve")
    ap.add_argument("--groupe", metavar="G",
                    help="couverture d'UN groupe : exit 0 si toute tâche cochée à preuve est "
                         "couverte par un enregistrement PASS (dette vide), 1 sinon — lu par "
                         "scripts/audit_registre.py (statut « accepté »)")
    return ap


def _mode_groupe(groupe: str, a_couvrir: dict, couverts: set, dette: dict) -> int:
    g = groupe.upper()
    ids = {i for i in a_couvrir if groupe_de(i) == g}
    non_couverts = sorted(ids - couverts, key=_cle)
    print(f"{g} : {len(ids)} cochée(s) à preuve, {len(ids & couverts)} couverte(s), "
          f"{len(non_couverts)} non couverte(s) (dette {len(dette.get(g, set()))})")
    return 0 if not non_couverts and not dette.get(g) else 1


def _mode_amorcer(restants: dict, dette: dict) -> int:
    sha = (_git("rev-parse", "--short=9", "HEAD") or "inconnu").strip()
    for groupe, ids in sorted(restants.items()):
        if groupe in dette:
            print(f"{groupe} : dette déjà amorcée — ignorée (elle ne fait que rétrécir)")
            continue
        ecrire_dette(groupe, ids, sha)
        print(f"{groupe} : dette amorcée à {sha} ({len(ids)} id(s))")
    return 0


def _mode_baseline(restants: dict, dette: dict) -> int:
    for groupe, ids in sorted(dette.items()):
        garde = ids & restants.get(groupe, set())
        if garde != ids:
            amorce = plan_lanes._MiniYamlParser((ROOT / DOSSIER / groupe / "_dette.yml")
                                                .read_text(encoding="utf-8")).parse()
            ecrire_dette(groupe, garde, str(amorce.get("amorce") or "inconnu"))
            print(f"{groupe} : dette rétrécie de {len(ids) - len(garde)} id(s) "
                  f"→ {len(garde)}")
    return 0


def _erreurs_garde(a_couvrir: dict, couverts: set, dette: dict, restants: dict,
                   base: str) -> list:
    erreurs = []
    for ident in sorted(a_couvrir, key=_cle):
        groupe = groupe_de(ident)
        if ident not in couverts and ident not in dette.get(groupe, set()):
            tache = a_couvrir[ident]
            erreurs.append(f"{ident} ({_rel(tache.fichier)}:{tache.ligne}) : cochée à preuve "
                           f"en direct, ni couverte par un enregistrement PASS ni dans la "
                           f"dette {groupe} — l'orchestrateur rejoue l'acceptation et "
                           f"commite l'enregistrement (CLAUDE.md 3-bis)")
    for groupe, ids in sorted(dette.items()):
        perimes = ids - restants.get(groupe, set())
        if perimes:
            erreurs.append(f"dette {groupe} : {len(perimes)} id(s) couvert(s) ou plus cochés "
                           f"à preuve ({', '.join(sorted(perimes, key=_cle))}) — lancez "
                           "`python scripts/check_acceptation.py --write-baseline`")
    if base_disponible(base):
        erreurs += croissances(base, dette)
    else:
        print(f"Avis : base « {base} » indisponible — croissance de la dette non "
              "vérifiée.")
    return erreurs


def _afficher_bilan(a_couvrir: dict, couverts: set, dette: dict):
    print("Acceptation par groupe (cochées à preuve / couvertes / en dette) :")
    for groupe in sorted({groupe_de(i) for i in a_couvrir} | set(dette)):
        ids = {i for i in a_couvrir if groupe_de(i) == groupe}
        print(f"  {groupe} : {len(ids)} cochée(s) à preuve, {len(ids & couverts)} "
              f"couverte(s), {len(dette.get(groupe, set()))} en dette")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = _parser().parse_args(argv)

    erreurs: list = []
    a_couvrir = taches_a_preuve()
    couverts = enregistrements(erreurs)
    dette = dettes()
    restants: dict = {}
    for ident in a_couvrir:
        if ident not in couverts:
            restants.setdefault(groupe_de(ident), set()).add(ident)

    if args.groupe:
        return _mode_groupe(args.groupe, a_couvrir, couverts, dette)
    if args.amorcer:
        return _mode_amorcer(restants, dette)
    if args.write_baseline:
        return _mode_baseline(restants, dette)

    erreurs += _erreurs_garde(a_couvrir, couverts, dette, restants, args.base)
    _afficher_bilan(a_couvrir, couverts, dette)
    if not erreurs:
        print("OK — toute tâche cochée à preuve est couverte ou en dette gelée.")
        return 0
    print(f"\nÉCHEC — {len(erreurs)} problème(s) d'acceptation :")
    for ligne in erreurs:
        print(f"  - {ligne}")
    return 0 if args.rapport else 1


if __name__ == "__main__":
    sys.exit(main())
