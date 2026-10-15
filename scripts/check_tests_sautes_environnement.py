#!/usr/bin/env python3
"""GARDE CI (stage-names) — ENF23 : tout test sauté est un saut d'ENVIRONNEMENT signé.

Un test n'est sauté que si une dépendance/un service externe est absent de
l'environnement (bibliothèque optionnelle, PostgreSQL seul, arbre partiel dans
le conteneur, test réseau désarmé règle #5, interrupteur de capture golden) —
jamais pour cause de bug ou de dette. Chaque site de saut (décorateur
`skip*` ou appel `skipTest`/`skip`) de `backend/` doit figurer dans
`scripts/exceptions_permanentes.yml` (catégorie `tests_sautes_environnement`,
clé `fichier::symbole`, entrées groupées par condition en commentaire).
Échec : site non signé, ou entrée périmée (le saut n'existe plus).

Usage : python scripts/check_tests_sautes_environnement.py [--emit]
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _exceptions_permanentes as ep  # noqa: E402 — après sys.path/setup() (D-ENF22)

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
CAT = "tests_sautes_environnement"
DECOS = {"skip", "skipIf", "skipUnless"}


def _est_test(p: Path) -> bool:
    n = p.name
    return p.suffix == ".py" and (
        n.startswith("test") or "tests" in p.parts) and "node_modules" not in p.parts


def _nom(n: ast.AST) -> str:
    return n.attr if isinstance(n, ast.Attribute) else getattr(n, "id", "")


def _sites_fichier(chemin: Path) -> dict[str, str]:
    try:
        source = chemin.read_text(encoding="utf-8")
        arbre = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return {}
    texte = source.splitlines()
    rel = chemin.relative_to(ROOT).as_posix()
    sites: dict[str, str] = {}

    def vu(pile, noeud):
        cle = f"{rel}::{'.'.join(pile) or '<module>'}"
        sites.setdefault(cle, texte[noeud.lineno - 1].strip())

    def visite(noeud, pile):
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                sous = pile + [enfant.name]
                for d in enfant.decorator_list:
                    c = d.func if isinstance(d, ast.Call) else d
                    if _nom(c) in DECOS:
                        vu(sous, d)
                visite(enfant, sous)
            else:
                if isinstance(enfant, ast.Call) and _nom(enfant.func) in {"skipTest", "skip"}:
                    vu(pile, enfant)
                visite(enfant, pile)

    visite(arbre, [])
    return sites


def sites() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(BACKEND.rglob("*.py")):
        if _est_test(p):
            out.update(_sites_fichier(p))
    return out


def main() -> int:
    trouves = sites()
    if "--emit" in sys.argv:
        for k, v in trouves.items():
            print(f"{k}\t{v}")
        return 0
    signes = ep.charger(CAT)
    non_signes = sorted(set(trouves) - signes)
    perimes = sorted(signes - set(trouves))
    for k in non_signes:
        print(f"saut NON SIGNÉ : {k}  ({trouves[k]})")
    for k in perimes:
        print(f"entrée périmée (plus de saut) : {k}")
    if non_signes or perimes:
        print("check_tests_sautes_environnement: ÉCHEC — réparer le test ou signer "
              "l'environnement dans scripts/exceptions_permanentes.yml.")
        return 1
    print(f"check_tests_sautes_environnement: OK — {len(trouves)} saut(s), tous signés (environnement).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
