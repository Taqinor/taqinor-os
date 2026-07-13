# Convention d'arrondi monétaire (YDATA8)

**Un seul point d'arrondi pour toute valeur en dirhams (MAD) :
`core.money.quantize_mad(value)`.**

## Pourquoi

- `round()` sur un `float` hérite de l'imprécision binaire IEEE-754
  (`round(2.675, 2)` vaut `2.67` en Python, pas `2.68`) et applique le
  "banker's rounding" (arrondi au pair le plus proche) — pas la politique
  "moitié vers le haut" attendue en comptabilité marocaine.
- `Decimal.quantize(..., rounding=ROUND_HALF_UP)` est déterministe et exact :
  `quantize_mad(Decimal('1.005')) == Decimal('1.01')`.

## Règle

- Toute valeur MONÉTAIRE finale (prix, montant, total HT/TTC, TVA, remise,
  acompte, solde…) affichée, stockée, ou comparée doit passer par
  `quantize_mad()` avant d'être figée — jamais un `round(x, 2)` brut.
- Les valeurs TECHNIQUES (kWc, surface, watt, débit, HMT…) restent hors
  périmètre : `round()` reste approprié, ce ne sont pas des montants.
- `scripts/check_money_rounding.py` est un garde ADVISORY (v1) : il signale
  tout `round()` appliqué à une valeur d'apparence monétaire dans les
  modules de pricing/tax (`apps/ventes/services.py`,
  `apps/ventes/quote_engine/builder.py`, `apps/compta/services.py`) et
  recommande `quantize_mad`. Il ne réécrit RIEN — les correctifs unitaires
  du code existant sont matière `ERROR_PLAN`, pas de ce garde. Un `round()`
  argent PRÉ-EXISTANT est baseline-allowlisté (`scripts/check_money_rounding.py`
  génère la liste à l'initialisation) ; seul un NOUVEAU site échoue la CI.

## Exemple

```python
from decimal import Decimal
from core.money import quantize_mad

total_ttc = quantize_mad(total_ht * (1 + taux_tva))
```
