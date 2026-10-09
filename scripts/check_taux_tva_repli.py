#!/usr/bin/env python3
"""AMOT73 - garde de la classe « repli ``or 20`` qui avale le zero » (C-AMOT-006).

Un taux de TVA de 0 % est une VALEUR (export, vente exoneree) ; seul ``is None``
declenche un repli. ``taux_tva or 20`` transforme silencieusement 0 en 20.

La garde echoue sur tout ``BoolOp(Or)`` dans ``backend/django_core/apps/ventes/**``
dont un operande gauche NOMME ``taux_tva`` / ``tva`` (nom, attribut, cle de
sous-script ou ``.get("taux_tva", ...)``) et dont l'operande droit est un
litteral numerique ou ``Decimal(<litteral>)`` / ``float(<litteral>)`` NON NUL.

DEUX REGLES STRUCTURELLES seulement (aucune exception par ligne) :
  1. ``or 0`` (litteral zero) est tolere : idempotent sur zero ;
  2. ``migrations/**`` est ignore (migrations gelees, jamais reecrites).

Analyse AST, DB-free, lecture seule. Sortie non nulle nommant fichier:ligne.

Usage : python scripts/check_taux_tva_repli.py
"""
from __future__ import annotations

import ast
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENTES = ROOT / "backend" / "django_core" / "apps" / "ventes"
NOMS_TVA = {"taux_tva", "tva"}

#: DETTE reelle trouvee a la pose de la garde dans du code ventes (session
#: proprietaire = ventes ; jamais corrigee depuis cette garde). Cle de CONTENU
#: ``fichier::expression`` (pas de ligne) ; une entree sans site est perimee et
#: fait echouer la garde. A retirer en corrigeant le site (`is None`).
A_CORRIGER = {
    "backend/django_core/apps/ventes/quote_engine/generate_devis_premium.py"
    "::data.get('taux_tva', 20) or 20":
        "A CORRIGER (session ventes/moteur) : un taux_tva = 0 transmis au "
        "moteur de rendu devient 20 % (data.get(..., 20) or 20)",
}


def _nomme_tva(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and n.id in NOMS_TVA:
            return True
        if isinstance(n, ast.Attribute) and n.attr in NOMS_TVA:
            return True
        if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                and n.value in NOMS_TVA:
            return True
    return False


def _valeur(node: ast.AST):
    """Valeur numerique d'un litteral ou ``Decimal/float/int(<litteral>)``."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = _valeur(node.operand)
        return None if v is None else (-v if isinstance(node.op, ast.USub) else v)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return Decimal(str(node.value))
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return Decimal(node.value)
        except InvalidOperation:
            return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in ("Decimal", "float", "int") and len(node.args) == 1:
        return _valeur(node.args[0])
    return None


def trouver(source: str):
    """-> liste de (ligne, texte) des replis ``tva or <non nul>``."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)):
            continue
        for i in range(1, len(n.values)):
            if not _nomme_tva(n.values[i - 1]):
                continue
            v = _valeur(n.values[i])
            if v is not None and v != 0:
                out.append((n.lineno, ast.unparse(n)))
                break
    return out


def _fichiers(base: Path):
    for p in sorted(base.rglob("*.py")):
        if "migrations" in p.relative_to(base).parts:
            continue
        yield p


def main(argv=None) -> int:
    violations = []
    utilises = set()
    for p in _fichiers(VENTES):
        for ligne, texte in trouver(p.read_text(encoding="utf-8")):
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
            cle = f"{rel}::{texte}"
            if cle in A_CORRIGER:
                utilises.add(cle)
                continue
            violations.append(f"{rel}:{ligne}: repli TVA « {texte} » avale le 0 % "
                              f"(utiliser `is None`)")
    for cle in sorted(set(A_CORRIGER) - utilises):
        violations.append(f"entree A_CORRIGER perimee (plus de site) : {cle}")
    if violations:
        print("\n".join(violations))
        return 1
    print("check_taux_tva_repli : OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
