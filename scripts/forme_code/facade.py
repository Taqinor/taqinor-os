"""Regle FACADE — pas de NOUVEAU re-export `# noqa: F401` ni d'alias de nom importe.

Jugee sur les NOMS neufs (prototype a 2/10 quand il jugeait les lignes). Hors champ : tests,
`import x` nu, sous-module (effet de bord : signaux), re-export d'un symbole deplace (SPL).
"""
from __future__ import annotations

import ast
import re
from pathlib import PurePosixPath

from .socle import Constat

NOQA_F401 = re.compile(r"#\s*noqa\s*:[^#\n]*\bF401\b")
RACINES = ("backend/django_core", "scripts", "backend", "")


def _est_test(chemin: str) -> bool:
    nom = PurePosixPath(chemin).name
    return "/tests/" in f"/{chemin}" or nom.startswith(("test_", "tests_")) or nom in ("tests.py", "conftest.py")


def _sous_module(ctx, chemin: str, noeud, nom: str) -> bool:
    parties = (noeud.module or "").split(".") if noeud.module else []
    parents = PurePosixPath(chemin).parents
    if noeud.level > len(parents):
        return False
    bases = [parents[noeud.level - 1].as_posix()] if noeud.level else list(RACINES)
    arbre = ctx.arbre_tete()
    for b in bases:
        dossier = "/".join(p for p in [b, *parties, nom] if p and p != ".")
        if f"{dossier}.py" in arbre or f"{dossier}/__init__.py" in arbre:
            return True
    return False


def facades(ctx, chemin: str, fichier) -> dict:
    """{nom expose: origine} : imports `from` marques noqa F401 + alias `A = nom_importe`."""
    if fichier is None or fichier.arbre is None:
        return {}
    lignes, sortie, importes = fichier.texte.splitlines(), {}, set()
    for n in fichier.arbre.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            importes |= {(a.asname or a.name).split(".")[0] for a in n.names}
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                and isinstance(n.value, ast.Name) and n.value.id in importes \
                and not n.targets[0].id.startswith("_") and n.targets[0].id != n.value.id:
            sortie[n.targets[0].id] = f"alias de {n.value.id}"
    for n in ast.walk(fichier.arbre):
        if not isinstance(n, ast.ImportFrom) or not any(
                NOQA_F401.search(lignes[i - 1]) for i in range(n.lineno, (n.end_lineno or n.lineno) + 1)):
            continue
        for a in n.names:
            if a.name != "*" and not _sous_module(ctx, chemin, n, a.name):
                sortie[a.asname or a.name] = f"from {'.' * n.level}{n.module or ''} import {a.name}"
    return sortie


def verifier(ctx) -> list:
    constats = []
    for c, base, tete in ctx.paires_py():
        if _est_test(c.apres):
            continue
        anciens = facades(ctx, c.avant, base) if base else {}
        partis = {q.split(".")[0] for f, q in ctx.deplaces.sortis if f == c.apres}
        for nom, origine in sorted(facades(ctx, c.apres, tete).items()):
            if nom not in anciens and nom not in partis:
                constats.append(Constat("FACADE", c.apres, nom, (
                    f"nouvelle façade ({origine}, # noqa: F401 / alias) : importer depuis le module "
                    "propriétaire au lieu d'exposer un nom de plus")))
    return constats
