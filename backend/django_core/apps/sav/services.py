"""
Helpers SAV — arithmétique de garantie (sans dépendance externe).

`add_months` ajoute un nombre de mois à une date en restant dans la stdlib
(calendar), avec recadrage du jour pour les fins de mois (ex. 31 jan + 1 mois
→ 28/29 fév). Sert au calcul des dates de fin de garantie des équipements.
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
