#!/usr/bin/env python3
"""GARDE CI (stage-names) — ACAL321 : un seul écrivain de `Calepinage.resultat`.

CLASSE C-ACAL-055 : « écrivain unique d'un sac JSON ». `Calepinage.resultat`
(le calcul stocké) ne s'écrit que par `services/resultat.py::modifier_resultat`
(et `services/layout.py`, qui invalide/pose le calcul en même temps que le
document). Toute autre affectation `<x>.resultat = …` ou
`save(update_fields=[…, 'resultat', …])` contourne l'empreinte, le journal et
la péremption du calcul.

La garde lit par AST `backend/django_core/apps/calepinage` (hors tests, hors
migrations, hors `services/resultat.py` et `services/layout.py`) et échoue en
nommant fichier:ligne. Passif gelé : `scripts/resultat_ecrivain_allow.txt`
(clé `fichier::fonction`, jamais un numéro de ligne) — il ne peut que
RÉTRÉCIR : `--write-baseline` REFUSE d'ajouter une ligne, une clé morte fait
échouer la garde.

Usage :
    python scripts/check_resultat_ecrivain_unique.py
    python scripts/check_resultat_ecrivain_unique.py --write-baseline
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = Path("backend") / "django_core" / "apps" / "calepinage"
BASELINE_PATH = ROOT / "scripts" / "resultat_ecrivain_allow.txt"
EXEMPTS = {"services/resultat.py", "services/layout.py"}
ENTETE = (
    "# Base de reference de check_resultat_ecrivain_unique.py (ACAL321).\n"
    "# Une ligne = `fichier::fonction` qui ecrit encore Calepinage.resultat hors\n"
    "# services/resultat.py::modifier_resultat. DETTE : ne peut que RETRECIR\n"
    "# (--write-baseline refuse d'ajouter ; --autoriser-croissance = fondateur).\n"
)


def _est_exclu(rel: Path) -> bool:
    parts = rel.parts
    return ("tests" in parts or "migrations" in parts
            or rel.name.startswith(("test_", "tests_"))
            or rel.name in ("tests.py", "conftest.py"))


class _Visiteur(ast.NodeVisitor):
    def __init__(self):
        self.pile: list = []
        self.sites: list = []  # (fonction, ligne)

    def _fn(self):
        return ".".join(self.pile) or "<module>"

    def _def(self, node):
        self.pile.append(node.name)
        self.generic_visit(node)
        self.pile.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _def

    def _cibles(self, node, cibles):
        for c in cibles:
            for el in (c.elts if isinstance(c, (ast.Tuple, ast.List)) else [c]):
                if isinstance(el, ast.Attribute) and el.attr == "resultat":
                    self.sites.append((self._fn(), node.lineno))
        self.generic_visit(node)

    def visit_Assign(self, node):
        self._cibles(node, node.targets)

    def visit_AugAssign(self, node):
        self._cibles(node, [node.target])

    def visit_AnnAssign(self, node):
        self._cibles(node, [node.target])

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "save":
            for kw in node.keywords:
                if kw.arg == "update_fields" and isinstance(
                        kw.value, (ast.List, ast.Tuple, ast.Set)):
                    if any(isinstance(e, ast.Constant) and e.value == "resultat"
                           for e in kw.value.elts):
                        self.sites.append((self._fn(), node.lineno))
        self.generic_visit(node)


def analyser(root: Path = ROOT) -> dict:
    """{clé 'fichier::fonction': ligne}."""
    base = root / APP
    trouves: dict = {}
    if not base.is_dir():
        return trouves
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(base)
        if _est_exclu(rel) or rel.as_posix() in EXEMPTS:
            continue
        try:
            arbre = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        v = _Visiteur()
        v.visit(arbre)
        fichier = path.relative_to(root).as_posix()
        for fonction, ligne in v.sites:
            trouves.setdefault(f"{fichier}::{fonction}", ligne)
    return trouves


def charger_base(path: Path = BASELINE_PATH) -> set:
    if not path.is_file():
        return set()
    out = set()
    for ligne in path.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            out.add(ligne)
    return out


def ecrire_base(cles: set, path: Path = BASELINE_PATH, base_actuelle: set | None = None,
                autoriser_croissance: bool = False) -> None:
    base_actuelle = charger_base(path) if base_actuelle is None else base_actuelle
    ajouts = set(cles) - base_actuelle
    if ajouts and not autoriser_croissance:
        raise ValueError("la base ne peut que RETRECIR ; ajouts refusés : "
                         + ", ".join(sorted(ajouts)))
    corps = "".join(f"{c}  # ACAL321 : écrit Calepinage.resultat hors modifier_resultat\n"
                    for c in sorted(cles))
    path.write_text(ENTETE + corps, encoding="utf-8", newline="\n")


def verifier(trouves: dict, base: set) -> list:
    erreurs = []
    for cle, ligne in sorted(trouves.items()):
        if cle not in base:
            fichier, fonction = cle.split("::", 1)
            erreurs.append(f"{fichier}:{ligne} ({fonction}) écrit Calepinage.resultat "
                           "hors services/resultat.py::modifier_resultat — "
                           "passer par modifier_resultat.")
    for cle in sorted(base - set(trouves)):
        erreurs.append(f"entrée MORTE de resultat_ecrivain_allow.txt : {cle} "
                       "(plus d'écriture directe — relancez --write-baseline).")
    return erreurs


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write-baseline", action="store_true")
    ap.add_argument("--autoriser-croissance", action="store_true")
    args = ap.parse_args(argv)
    trouves = analyser()
    base = charger_base()
    if args.write_baseline:
        try:
            ecrire_base(set(trouves), base_actuelle=base,
                        autoriser_croissance=args.autoriser_croissance
                        or not BASELINE_PATH.is_file())
        except ValueError as exc:
            print("REFUS : " + str(exc))
            return 1
        print(f"Base réécrite ({len(trouves)} entrée(s)).")
        return 0
    erreurs = verifier(trouves, base)
    if erreurs:
        print("check_resultat_ecrivain_unique: ÉCHEC")
        for e in erreurs:
            print("  - " + e)
        return 1
    print(f"check_resultat_ecrivain_unique: OK — {len(trouves)} écriture(s) "
          "directe(s) historique(s) gelée(s), aucune nouvelle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
