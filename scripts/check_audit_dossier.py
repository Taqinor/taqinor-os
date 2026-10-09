#!/usr/bin/env python3
"""Lint de dossier d'audit v3 (AMET92, METHODE v3 §C.3).

    python scripts/check_audit_dossier.py [dossier.md ...]   # defaut : tous les v3
    python scripts/check_audit_dossier.py --methode          # plafonds de longueur

Le gabarit `docs/audits/GABARIT_DOSSIER.md` est la SOURCE UNIQUE des regles : ce
script en lit l'ordre des `##`, les en-tetes de tableaux, les plafonds de taille et
les motifs interdits (aucune seconde copie). Les criteres a sonde obligatoire en
S1-S2 sont lus dans le tableau §A.4 de METHODE.md. Ne s'applique qu'aux fichiers
dont l'en-tete porte `<!-- dossier-v3` ; les dossiers v2 sont ignores.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check_taches_cablage as ctc  # noqa: E402
from plan_lanes import _MiniYamlParser  # noqa: E402

ROOT = HERE.parent
GABARIT = "docs/audits/GABARIT_DOSSIER.md"
METHODE = "docs/audits/METHODE.md"
SKILL = ".claude/skills/audit/SKILL.md"
PLAFOND_METHODE = 450
PLAFOND_SKILL = 80
_ID_TACHE = re.compile(r"\b[A-Z]{2,}[A-Z0-9]*\d+\b")
_FICHIER_LIGNE = re.compile(r"\.(?:py|jsx?|tsx?|md|ya?ml|sh|ps1|html|css|json):\d+")


def _lire(rel: str) -> str:
    chemin = ROOT / rel
    return chemin.read_text(encoding="utf-8") if chemin.is_file() else ""


def _cellules(ligne: str) -> list:
    brut = ligne.strip().replace("\\|", "\x00")
    return [c.replace("\x00", "|").strip() for c in brut.strip("|").split("|")]


def _norm_cellule(cellule: str) -> str:
    return re.sub(r"`[^`]*`|\([^)]*\)", "", cellule).strip()


def regles_du_gabarit() -> dict:
    """Extrait du gabarit : sections, en-tetes, plafonds, interdits."""
    texte = _lire(GABARIT)
    squelette = texte.split("## Squelette", 1)[-1]
    sections, entetes, courante = [], {}, None
    for ligne in squelette.splitlines():
        if re.match(r"^## \d+\. ", ligne):
            courante = ligne.strip()
            sections.append(courante)
        elif courante and ligne.startswith("|") and courante not in entetes:
            entetes[courante] = [_norm_cellule(c) for c in _cellules(ligne)]
    regles = texte.split("## Règles", 1)[-1].split("## Squelette", 1)[0]

    def entier(motif, defaut):
        m = re.search(motif, regles)
        return int(m.group(1)) if m else defaut

    r4 = re.search(r"^4\. .*?(?=^5\. )", regles, re.S | re.M)
    r4 = r4.group(0) if r4 else ""
    motifs = [m for m in re.findall(r"`([^`]+)`", r4) if "\\" in m or "^" in m]
    litteraux = [re.sub(r"\s+", " ", m).strip()
                 for m in re.findall(r"«\s*([^»]+?)\s*»", r4)]
    return {
        "sections": sections, "entetes": entetes,
        "ligne_max": entier(r"lignes ≤ (\d+) caract", 400),
        "hors_tableau": entier(r"hors tableau §3 ≤ (\d+) Ko", 12) * 1024,
        "base_total": entier(r"total ≤ (\d+) Ko", 12) * 1024,
        "par_constat": entier(r"Ko \+ (\d+) o", 400),
        "bloc_max": entier(r"blocs de code > (\d+) lignes", 5),
        "motifs": motifs, "litteraux": litteraux,
        "cout": (re.search(r"suit `([^`]+)`", regles) or [None, None])[1],
        "lane_col1": "1re colonne du §2" in r4,
    }


def criteres_a_sonde() -> set:
    trouves = set()
    for ligne in _lire(METHODE).splitlines():
        m = re.match(r"^\|\s*(C\d+)\s*\|", ligne)
        if m and ligne.rstrip().rstrip("|").rsplit("|", 1)[-1].strip().startswith("oui"):
            trouves.add(m.group(1))
    return trouves


def dossiers_v3() -> list:
    sortie = []
    for chemin in sorted((ROOT / "docs" / "audits").glob("*.md")):
        if chemin.name in ("GABARIT_DOSSIER.md", "METHODE.md"):
            continue
        tete = "\n".join(chemin.read_text(encoding="utf-8").splitlines()[:5])
        if re.search(r"<!--\s*dossier-v3\b", tete):
            sortie.append(chemin)
    return sortie


def _tache_existe(ident: str, ids: set, archive: str) -> bool:
    return ident in ids or re.search(rf"\b{re.escape(ident)}\b", archive) is not None


def regle_sonde(rid, grav, crit, cellule, groupe, a_sonde) -> list:
    """Colonne Sonde : chemin EXISTANT ou STATIQUE (interdit en S1-S2 a sonde)."""
    if cellule.startswith("STATIQUE"):
        if grav in ("S1", "S2") and crit in a_sonde:
            return [f"{rid} : STATIQUE interdit en {grav} sur le critère {crit} "
                    "(sonde obligatoire, METHODE §A.4)."]
        return []
    chemin = re.search(rf"`?(docs/audits/sondes/{re.escape(groupe)}/"
                       rf"{re.escape(rid)}\.py)`?", cellule)
    if not chemin:
        return [f"{rid} : colonne Sonde « {cellule[:50]} » = ni STATIQUE ni "
                f"docs/audits/sondes/{groupe}/{rid}.py."]
    if not (ROOT / chemin.group(1)).is_file():
        return [f"{rid} : sonde {chemin.group(1)} introuvable."]
    return []


def analyser(chemin: Path) -> list:
    g = regles_du_gabarit()
    nom = chemin.name
    texte = chemin.read_text(encoding="utf-8")
    lignes = texte.splitlines()
    erreurs = []

    def err(n, msg):
        erreurs.append(f"{nom}:{n} : {msg}" if n else f"{nom} : {msg}")

    entete = next((m for m in (re.search(r"<!--\s*dossier-v3\s*\|(.*?)-->", ln)
                               for ln in lignes[:5]) if m), None)
    cles = dict(re.findall(r"(\w+):\s*([^|]+?)\s*(?:\||$)", entete.group(1))) \
        if entete else {}
    for k in ("groupe", "base", "fraicheur", "constats", "taches", "decisions"):
        if k not in cles:
            err(2, f"en-tête incomplet : clé « {k} » absente.")
    groupe = cles.get("groupe", "")

    # Regle 1 : ordre des sections et en-tetes de tableaux.
    titres = [(i, l.strip()) for i, l in enumerate(lignes, 1)
              if re.match(r"^## \d+\. ", l)]
    if [t for _, t in titres] != g["sections"]:
        err(0, "ordre des sections : attendu " + " / ".join(
            s.split(". ", 1)[0].lstrip("# ") for s in g["sections"]) + ", lu "
            + " / ".join(t.split(". ", 1)[0].lstrip("# ") for _, t in titres)
            + " (titres du gabarit).")
    bornes = {t: (i, titres[k + 1][0] if k + 1 < len(titres) else len(lignes) + 1)
              for k, (i, t) in enumerate(titres)}
    for titre, attendu in g["entetes"].items():
        if titre not in bornes:
            continue
        debut, fin = bornes[titre]
        premier = next(((i, l) for i, l in enumerate(lignes, 1)
                        if debut < i < fin and l.startswith("|")), None)
        if not premier or [_norm_cellule(c) for c in _cellules(premier[1])] != attendu:
            err(premier[0] if premier else debut,
                f"en-tête de tableau de « {titre} » différent du gabarit.")

    # Regle 2 : tailles.
    for i, l in enumerate(lignes, 1):
        if len(l) > g["ligne_max"]:
            err(i, f"ligne de {len(l)} caractères (plafond {g['ligne_max']}).")
    s3 = next((t for t in bornes if t.startswith("## 3.")), None)
    lignes_s3 = set()
    rows = []
    if s3:
        debut, fin = bornes[s3]
        for i in range(debut + 1, fin):
            if re.match(r"^\|\s*C-[A-Z0-9]+-\d+\b", lignes[i - 1]):
                lignes_s3.add(i)
                rows.append((i, _cellules(lignes[i - 1])))
    hors = sum(len(l.encode("utf-8")) + 1 for i, l in enumerate(lignes, 1)
               if i not in lignes_s3)
    if hors > g["hors_tableau"]:
        err(0, f"{hors} o hors tableau §3 (plafond {g['hors_tableau']} o).")
    total = len(texte.encode("utf-8"))
    if total > g["base_total"] + g["par_constat"] * len(rows):
        err(0, f"{total} o au total (plafond {g['base_total']} o + "
               f"{g['par_constat']} o × {len(rows)} constats).")

    # Regle 4 : interdits.
    motifs = [re.compile(m) for m in g["motifs"]]
    litt = [re.compile(re.escape(x), re.I) for x in g["litteraux"]]
    courriel = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
    tel = re.compile(r"(?:\+|00)\d{2,3}[\s.-]?\d(?:[\s.-]?\d{2}){4}|"
                     r"\b0[5-7](?:[\s.-]?\d{2}){4}\b")
    scratch = re.compile(r"scratchpad|AppData[\\/]Local[\\/]Temp|/tmp/claude", re.I)
    dans_s2 = bornes.get(next((t for t in bornes if t.startswith("## 2.")), ""))
    bloc, debut_bloc = 0, 0
    for i, l in enumerate(lignes, 1):
        if l.strip().startswith("```"):
            if bloc:
                if i - debut_bloc - 1 > g["bloc_max"]:
                    err(debut_bloc, f"bloc de code de {i - debut_bloc - 1} lignes "
                        f"(> {g['bloc_max']} : les sondes vont dans sondes/).")
                bloc = 0
            else:
                bloc, debut_bloc = 1, i
            continue
        vu = l
        if g["lane_col1"] and dans_s2 and dans_s2[0] < i < dans_s2[1] \
                and l.startswith("|"):
            vu = "|" + "|".join(_cellules(l)[1:])
        for rx in motifs + litt + [courriel, tel, scratch]:
            if rx.search(vu):
                err(i, f"contenu interdit « {rx.search(vu).group(0)[:30]} » "
                    "(gabarit, règle 4).")
                break

    # Regles 3 et 5 : constats, taches, decisions.
    taches = ctc.lire_taches()
    ids = {t.identifiant for t in taches}
    archive = _lire("docs/done_task.md")
    cite = re.compile(rf"\bC-{re.escape(groupe)}-\d+\b(?!{{)")
    en_s3 = {c[0] for _, c in rows}
    citantes = [t for t in taches if cite.search(t.texte)]
    for t in citantes:
        for c in sorted(set(cite.findall(t.texte)) - en_s3):
            err(0, f"{c} cité par la tâche {t.identifiant} ({t.fichier}) mais "
                   "absent du §3.")
    a_sonde = criteres_a_sonde()
    cites = 0
    for i, c in rows:
        if len(c) != 8:
            err(i, f"{c[0]} : {len(c)} colonnes au lieu de 8.")
            continue
        rid, _, crit, grav, ancre, _, sonde, tc = c
        if _FICHIER_LIGNE.search(ancre):
            err(i, f"{rid} : ancre « {ancre[:40]} » en fichier:ligne — "
                   "utiliser fichier::symbole.")
        for e in regle_sonde(rid, grav, crit, sonde, groupe, a_sonde):
            err(i, e)
        idents = _ID_TACHE.findall(tc)
        manquants = [x for x in idents if not _tache_existe(x, ids, archive)]
        for x in manquants:
            err(i, f"{rid} : tâche {x} introuvable dans les plans.")
        sans = re.search(r"sans tâche\s*:\s*\S", tc) or "§7" in tc
        if not idents and not sans:
            err(i, f"{rid} ({grav}) : ni tâche ni « sans tâche : raison ».")
        cites += bool(idents)
    # Regle 5 : decisions.
    decisions = {d.get("id") for d in (_MiniYamlParser(
        _lire("docs/audits/decisions.yml")).parse().get("decisions") or [])}
    n_dec = 0
    s6 = next((t for t in bornes if t.startswith("## 6.")), None)
    if s6:
        for i in range(bornes[s6][0] + 1, bornes[s6][1]):
            m = re.match(r"^\|\s*(D-[A-Z0-9-]+)\s*\|", lignes[i - 1])
            if m:
                n_dec += 1
                if m.group(1) not in decisions:
                    err(i, f"décision {m.group(1)} absente de decisions.yml.")
    for t in taches:
        if t.identifiant.startswith(groupe) and t.etat.strip() == "" and re.search(
                r"(?<![«`\"])(?<!« )Si \(a\)", t.texte):
            err(0, f"tâche {t.identifiant} contient « Si (a) » (une tâche par option).")
    # Regle 6 : cout.
    s9 = next((t for t in bornes if t.startswith("## 9.")), None)
    if s9 and g["cout"]:
        corps = "\n".join(lignes[bornes[s9][0]:bornes[s9][1] - 1])
        if not re.search(g["cout"].replace("\\d", r"\d"), corps):
            err(bornes[s9][0], "ligne de coût absente ou mal formée (règle 6 : "
                f"`{g['cout']}`).")
    # Compteurs de l'en-tete.
    for cle, vrai in (("constats", len(rows)), ("decisions", n_dec),
                      ("taches", len(citantes))):
        if cle in cles and cles[cle].isdigit() and int(cles[cle]) != vrai:
            err(2, f"en-tête {cle}: {cles[cle]} mais {vrai} réels.")
    return erreurs


def verifier_methode() -> list:
    erreurs = []
    for rel, plafond in ((METHODE, PLAFOND_METHODE), (SKILL, PLAFOND_SKILL)):
        n = len(_lire(rel).splitlines())
        if n > plafond:
            erreurs.append(f"{rel} : {n} lignes (plafond {plafond}).")
    return erreurs


def main(argv=None) -> int:
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8")
    a = list(sys.argv[1:] if argv is None else argv)
    if a == ["--methode"]:
        erreurs = verifier_methode()
    else:
        cibles = [Path(x).resolve() for x in a] or dossiers_v3()
        erreurs = [e for c in cibles for e in analyser(c)]
    for e in erreurs:
        print(f"ERREUR dossier d'audit : {e}")
    if not erreurs:
        print("Dossiers d'audit v3 conformes au gabarit."
              if a != ["--methode"] else "METHODE et SKILL sous leurs plafonds.")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
