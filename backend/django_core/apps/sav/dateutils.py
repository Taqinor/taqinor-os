"""Arithmétique de dates SAV, SANS dépendance à `sav.services`.

`add_months` vit ici (et non dans `services.py`) pour que `sav.models` puisse
l'importer sans tirer tout le module `services` — lequel appelle d'autres apps
(ex. `ventes.services`). Cela préserve le découplage M1 des modèles de domaine
(``sav.models`` ne doit atteindre aucun autre modèle de domaine, même
transitivement). Fonction pure, stdlib uniquement.
"""
import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    """Retourne `d` décalée de `months` mois (jour recadré sur la fin de mois)."""
    if d is None or months is None:
        return None
    total = d.month - 1 + int(months)
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
