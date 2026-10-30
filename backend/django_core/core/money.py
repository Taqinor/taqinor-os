"""YDATA8 — arrondi monétaire centralisé : UNE seule politique `quantize`.

`quantize_mad` est le SEUL point d'arrondi recommandé pour toute valeur en
dirhams (MAD) : `round()` sur un `float`/`Decimal` accumule des erreurs de
représentation binaire et n'a pas de politique d'arrondi explicite
(`round(2.675, 2)` vaut `2.67` en Python — banker's rounding sur les floats —
au lieu du "moitié vers le haut" attendu en compta). `quantize_mad` prend un
`Decimal` (ou tout ce qui se convertit proprement en `Decimal`) et applique
`ROUND_HALF_UP` à 2 décimales, la convention documentée dans
`docs/money-convention.md`.

Ne réécrit PAS la logique de pricing/tax existante (ce serait des correctifs
unitaires — matière ERROR_PLAN) : v1 = le helper + la convention, avec un
garde-fou advisory (`scripts/check_money_rounding.py`) qui signale les
`round()` sur une valeur monétaire dans les modules de pricing/tax.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def quantize_mad(value, decimales=2) -> Decimal:
    """Arrondit `value` à `decimales` décimales (2 = le centime MAD),
    moitié-vers-le-haut.

    D-ENF-ARRONDI-PDF (30/10/2026) — ``decimales`` garde la PRÉCISION d'un
    affichage existant (le dirham entier du PDF : ``decimales=0``) sans
    changer la politique : il n'y a toujours qu'UNE règle d'arrondi.

    Accepte un `Decimal`, un `int`, ou une chaîne (JAMAIS un `float` littéral
    passé directement en production — convertir via `str(x)` ou `Decimal(x)`
    en amont pour éviter l'imprécision binaire ; un `float` est néanmoins
    toléré ici, converti via `str()`, pour ne pas planter un appelant
    existant qui passerait encore un flottant).
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal(1).scaleb(-int(decimales)), rounding=ROUND_HALF_UP)
