#!/usr/bin/env python3
"""GARDE CI (stage-names) — ACAL341 : plus de test « squelette » qui ne prouve rien.

CLASSE C-ACAL-146 : un test sauté INCONDITIONNELLEMENT et dont le corps lève
`NotImplementedError` (ou est vide), ou dont la raison dit « CI validera » /
« non exécuté », est un faux vert à vie : il compte dans la suite et ne prouve
rien. La garde lit par AST tous les tests de `backend/django_core`
(`tests/`, `tests*.py`, `test_*.py`) et échoue en nommant fichier:ligne pour :

  (a) un `@unittest.skip(...)` / `@pytest.mark.skip(...)` INCONDITIONNEL
      (pas `skipIf` / `skipUnless`) dont le corps est `raise
      NotImplementedError` ou vide (`pass`, `...`, docstring seule) ;
  (b) une raison de skip (décorateur ou `self.skipTest(...)`) contenant
      « CI validera » ou « non exécuté » ;
  (c) un `raise NotImplementedError` dans un `test_*`.

Les skips CONDITIONNELS (`skipUnless` sur une dépendance) sont admis.
Passif gelé : `scripts/tests_skips_allow.txt` (clé `fichier::fonction`), il ne
peut que RÉTRÉCIR (`--write-baseline` refuse d'ajouter).

Usage :
    python scripts/check_tests_skips_inconditionnels.py [--write-baseline]
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
import unicodedata
from pathlib import Path
TYPE_DE_CLE = "par_symbole"  # AMET100 — cle de contenu `fichier::symbole` (jamais un numero de ligne)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _cliquet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BACKEND = Path("backend") / "django_core"
BASELINE = ROOT / "scripts" / "tests_skips_allow.txt"
ENTETE = (
    "# Base de reference de check_tests_skips_inconditionnels.py (ACAL341).\n"
    "# Une ligne = `fichier::fonction` d'un test squelette (skip inconditionnel +\n"
    "# NotImplementedError / raison « CI validera »). DETTE : ne peut que\n"
    "# RETRECIR (--write-baseline refuse d'ajouter).\n"
)
_RAISONS_INTERDITES = ("ci validera", "non execute")


def _normalise(texte: str) -> str:
    sans = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sans.lower())


def est_fichier_de_test(rel: Path) -> bool:
    return (rel.suffix == ".py"
            and ("tests" in rel.parts[:-1] or rel.name.startswith(("test_", "tests_"))
                 or rel.name == "tests.py")
            and "migrations" not in rel.parts and "node_modules" not in rel.parts)


def _nom_decorateur(dec) -> tuple:
    """(nom plat 'unittest.skip', est_appel, noeud d'appel|None)."""
    appel = dec if isinstance(dec, ast.Call) else None
    cible = dec.func if appel else dec
    morceaux = []
    while isinstance(cible, ast.Attribute):
        morceaux.append(cible.attr)
        cible = cible.value
    if isinstance(cible, ast.Name):
        morceaux.append(cible.id)
    return ".".join(reversed(morceaux)), appel


def _est_skip_inconditionnel(nom: str) -> bool:
    fin = nom.rsplit(".", 1)[-1]
    return fin == "skip" and not nom.endswith(("skipIf", "skipUnless"))


def _textes(noeud) -> list:
    return [c.value for c in ast.walk(noeud)
            if isinstance(c, ast.Constant) and isinstance(c.value, str)]


def _corps_vide(corps: list) -> bool:
    for n in corps:
        if isinstance(n, ast.Pass):
            continue
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant):
            continue
        return False
    return True


def _leve_not_implemented(fonction) -> bool:
    for n in ast.walk(fonction):
        if isinstance(n, ast.Raise) and n.exc is not None:
            cible = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            if isinstance(cible, ast.Name) and cible.id == "NotImplementedError":
                return True
    return False


def analyser_source(source: str) -> list:
    """[(fonction, ligne, regle)] des tests fautifs d'un texte Python."""
    if "skip" not in source and "NotImplementedError" not in source:
        return []  # préfiltre : l'immense majorité des fichiers n'a rien à lire
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return []
    sites = []
    for fn in ast.walk(arbre):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not fn.name.startswith("test"):
            continue
        skip_inconditionnel = False
        for dec in fn.decorator_list:
            nom, appel = _nom_decorateur(dec)
            if nom.endswith(("skipIf", "skipUnless")):
                continue
            if _est_skip_inconditionnel(nom):
                skip_inconditionnel = True
                raisons = _textes(appel) if appel else []
                if any(any(i in _normalise(t) for i in _RAISONS_INTERDITES)
                       for t in raisons):
                    sites.append((fn.name, fn.lineno, "b"))
        for appel in ast.walk(fn):
            if (isinstance(appel, ast.Call) and isinstance(appel.func, ast.Attribute)
                    and appel.func.attr == "skipTest"):
                if any(any(i in _normalise(t) for i in _RAISONS_INTERDITES)
                       for t in _textes(appel)):
                    sites.append((fn.name, fn.lineno, "b"))
        if _leve_not_implemented(fn):
            sites.append((fn.name, fn.lineno, "c"))
        elif skip_inconditionnel and _corps_vide(fn.body):
            sites.append((fn.name, fn.lineno, "a"))
    return sites


def analyser(root: Path = ROOT) -> dict:
    """{clé 'fichier::fonction': (ligne, règles)}."""
    base = root / BACKEND
    trouves: dict = {}
    if not base.is_dir():
        return trouves
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(base)
        if not est_fichier_de_test(rel):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for fonction, ligne, regle in analyser_source(source):
            cle = f"{path.relative_to(root).as_posix()}::{fonction}"
            ancien = trouves.get(cle)
            trouves[cle] = (ligne, (ancien[1] if ancien else "") + regle)
    return trouves


def verifier(trouves: dict, base: set) -> list:
    def decrire(cle):
        ligne, regles = trouves[cle]
        fichier, fonction = cle.split("::", 1)
        return (f"{fichier}:{ligne} {fonction} : test squelette (règle(s) "
                f"{', '.join(sorted(set(regles)))}) — écrivez le test ou supprimez-le.")
    return _cliquet.comparer(trouves, base, nom_fichier="tests_skips_allow.txt",
                             decrire=decrire)


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--autoriser-croissance", action="store_true")
    args = ap.parse_args(argv)
    trouves = analyser()
    if args.write_baseline:
        try:
            _cliquet.ecrire(BASELINE, trouves, ENTETE, "ACAL341 test squelette",
                            autoriser_croissance=args.autoriser_croissance)
        except ValueError as exc:
            print("REFUS : " + str(exc))
            return 1
        print(f"Base réécrite ({len(trouves)} entrée(s)).")
        return 0
    erreurs = verifier(trouves, _cliquet.charger(BASELINE))
    if erreurs:
        print("check_tests_skips_inconditionnels: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_tests_skips_inconditionnels: OK — {len(trouves)} test(s) "
          "squelette(s) gelé(s), aucun nouveau.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
