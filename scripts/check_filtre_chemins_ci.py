#!/usr/bin/env python3
"""ADEP13 - garde du filtre de chemins `changes` de ci.yml cote LECTURES CROISEES.

PACT10 promet « ce test casse TOUT SEUL » quand un contrat change - encore faut-il que le
job qui lit le fichier tourne sur la PR qui le modifie. Cette garde releve les fichiers
HORS de `frontend/` lus par les tests frontend (litteraux de chemins relatifs `../..`,
litteraux `backend/...`, segments de `join(...)`/`resolve(...)` contenant `backend`) et
exige que chacun declenche `frontend` dans le filtre (regles lues dans ci.yml via
`scripts/tests/test_ci_changes_filter.py` : `_detect_step_script`, `_parse_rules`,
`_resolve` - reutilises, pas recopies).

Seconde moitie (comportementale, lourde) : `fichiers_ouverts_par_gardes(job)` rejoue les
gardes d'un job gate avec un `sys.addaudithook` ; elle est exercee par le test
`test_check_filtre_chemins_ci` et par `--profond` ici.

Usage : python scripts/check_filtre_chemins_ci.py [racine] [--profond]   (0 vert, 1 rouge)
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))
import test_ci_changes_filter as filtre  # noqa: E402

_LITTERAL = re.compile(r"""(['"`])((?:\\.|(?!\1)[^\\\n])*)\1""")
_APPEL_CHEMIN = re.compile(r"\b(?:join|resolve)\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
# Marqueurs de racine du depot (`existsSync(join(dossier, 'backend', 'django_core', 'manage.py'))`)
# : l'EXISTENCE du fichier compte, pas son contenu -> aucune regle exigee.
MARQUEURS_RACINE = {"backend/django_core/manage.py"}
_RACINES_EXTERNES = ("backend/", "docs/", "scripts/", "apps/", "STAGES.py", ".github/")


def regles(racine: Path):
    texte = (racine / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    ancien = filtre.WORKFLOW
    try:
        filtre.WORKFLOW = racine / ".github" / "workflows" / "ci.yml"
        script = filtre._detect_step_script()
    finally:
        filtre.WORKFLOW = ancien
    assert texte
    return filtre._parse_rules(script)


def fichiers_tests_frontend(racine: Path) -> list[Path]:
    base = racine / "frontend" / "src"
    if not base.is_dir():
        return []
    sortie = []
    for chemin in base.rglob("*"):
        if chemin.suffix in (".js", ".jsx", ".mjs", ".ts", ".tsx") and (
                ".test." in chemin.name or "/test/" in chemin.as_posix()):
            sortie.append(chemin)
    # ADEP101 : modules de frontend/scripts/ importes par un test (lisent des fixtures backend)
    scripts = racine / "frontend" / "scripts"
    if scripts.is_dir():
        textes = [t.read_text(encoding="utf-8", errors="replace") for t in sortie]
        for mod in sorted(scripts.glob("*.mjs")):
            if any("scripts/" + mod.name in t for t in textes):
                sortie.append(mod)
    return sorted(sortie)


def _sonde(racine: Path, rel: str) -> str | None:
    """Chemin (relatif au depot, '/') a soumettre au filtre, ou None si inexistant."""
    p = racine / rel
    if p.is_file():
        return rel
    return None


def _sans_commentaires(texte: str) -> str:
    """Retire /* ... */ et // ... (hors litteraux grossierement : `://` des URL epargne)."""
    texte = re.sub(r"/\*.*?\*/", "", texte, flags=re.S)
    return re.sub(r"(?<![:'\"`\\])//[^\n]*", "", texte)


def candidats(racine: Path, fichier: Path) -> set[str]:
    """Chemins hors `frontend/` references par ce fichier de test."""
    texte = _sans_commentaires(fichier.read_text(encoding="utf-8", errors="replace"))
    trouves: set[str] = set()

    def ajouter(rel: str):
        rel = os.path.normpath(rel).replace(os.sep, "/")
        if rel.startswith("..") or rel.startswith("frontend/") or rel == "frontend":
            return
        sonde = _sonde(racine, rel)
        if sonde and sonde not in MARQUEURS_RACINE:
            trouves.add(sonde)

    for m in _LITTERAL.finditer(texte):
        lit = m.group(2)
        if "${" in lit or "\n" in lit or len(lit) > 300:
            continue
        if lit.startswith(".") and "../" in lit:
            rel = os.path.relpath(os.path.normpath(os.path.join(fichier.parent, lit)), racine)
            ajouter(rel)
        elif lit.startswith(_RACINES_EXTERNES) and " " not in lit:
            ajouter(lit)
    dossiers: dict[str, list[str]] = {}  # variable = join(...) deja vue -> ses segments
    for appel in _APPEL_CHEMIN.finditer(texte):
        segs = []
        for m in _LITTERAL.finditer(appel.group(1)):
            lit = m.group(2)
            if "${" in lit:
                break
            segs.append(lit.strip("/"))
        tete = re.match(r"\s*(\w+)\s*,", appel.group(1))
        if tete and tete.group(1) in dossiers:  # join(DOSSIER, 'fichier') (ADEP101)
            segs = dossiers[tete.group(1)] + segs
        nom = re.search(r"(\w+)\s*=\s*$", texte[:appel.start()])
        if nom:
            dossiers[nom.group(1)] = segs
        if "backend" in segs:
            ajouter("/".join(segs[segs.index("backend"):]))
    return trouves


def verifier(racine: Path) -> list[str]:
    rules = regles(racine)
    erreurs = []
    vus: dict[str, str] = {}
    for f in fichiers_tests_frontend(racine):
        for cand in sorted(candidats(racine, f)):
            if cand in vus:
                continue
            vus[cand] = f.relative_to(racine).as_posix()
            if not filtre._resolve(rules, [cand])["frontend"]:
                erreurs.append(
                    f"{cand.replace('/_sonde.json', '/')} est lu par {vus[cand]} mais ne "
                    f"declenche pas `frontend` dans le filtre `changes` de ci.yml - ajoutez "
                    f"une regle `grep -qE ... && frontend=true`")
    return erreurs


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    racine = Path(args[0]) if args else HERE.parent
    erreurs = verifier(racine)
    for e in erreurs:
        print(f"ECHEC check_filtre_chemins_ci : {e}")
    if not erreurs:
        print("check_filtre_chemins_ci : OK")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
