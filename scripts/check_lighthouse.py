#!/usr/bin/env python3
"""ENF12 — budgets Lighthouse BLOQUANTS du site vitrine (apps/web).

Lit un ou plusieurs rapports JSON Lighthouse (``--output=json``), prend la
MÉDIANE de chaque catégorie (le score perf d'une seule passe sur le serveur de
prévisualisation CI varie de 0,44 à 0,72) et rend 1 si une médiane passe sous
son budget, ou si une catégorie budgétée manque (la passe n'a pas tourné).

BUDGETS — mesurés sur les 4 passes nocturnes de main du 05 au 08/10/2026
(release-verify, job web-full) : performance 0,69 / 0,44 / 0,61 / 0,72,
accessibilité 0,93 ×4, bonnes pratiques 0,92 / 0,92 / 0,77 / 0,77, SEO 1 ×4.
Chaque budget = au plus le minimum mesuré, arrondi vers le bas : jamais rouge
le premier jour. À MONTER par paliers de 0,05 à mesure que les médianes
montent (la performance en premier) ; jamais à baisser.

Usage : python scripts/check_lighthouse.py rapport1.json [rapport2.json ...]
"""
from __future__ import annotations

import json
import statistics
import sys

BUDGETS = {
    "performance": 0.40,
    "accessibility": 0.90,
    "best-practices": 0.75,
    "seo": 0.95,
}


def medianes(rapports: list[dict]) -> dict[str, float | None]:
    sortie = {}
    for cat in BUDGETS:
        scores = [r.get("categories", {}).get(cat, {}).get("score") for r in rapports]
        scores = [s for s in scores if isinstance(s, (int, float))]
        sortie[cat] = statistics.median(scores) if scores else None
    return sortie


def evaluer(rapports: list[dict]) -> tuple[bool, list[str]]:
    lignes, ok = [], bool(rapports)
    if not rapports:
        lignes.append("ECHEC : aucun rapport Lighthouse — la passe n'a pas tourné.")
    for cat, med in medianes(rapports).items():
        budget = BUDGETS[cat]
        if med is None:
            ok = False
            lignes.append(f"ECHEC {cat} : score absent")
        elif med < budget:
            ok = False
            lignes.append(f"ECHEC {cat} : médiane {med:.2f} < budget {budget:.2f}")
        else:
            lignes.append(f"OK    {cat} : médiane {med:.2f} ≥ budget {budget:.2f}")
    return ok, lignes


def main(argv: list[str]) -> int:
    rapports = []
    for chemin in argv[1:]:
        try:
            with open(chemin, encoding="utf-8") as fh:
                rapports.append(json.load(fh))
        except (OSError, ValueError) as exc:
            print(f"ECHEC : rapport illisible {chemin} ({exc})")
            return 1
    ok, lignes = evaluer(rapports)
    print("\n".join(lignes))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
