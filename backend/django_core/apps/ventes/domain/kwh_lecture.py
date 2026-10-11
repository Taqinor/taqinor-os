"""QJR609 / ENF20 — UN lecteur de kWh sur une désignation, feuille PURE (n'importe que `re`).

``quote_engine.lignes_classement`` et ``domain.catalogue`` le lisent ici : ``utils.options``
ne tire plus le catalogue (qui lit ``stock.selectors``) et la garde SPL162 exige qu'aucun des
deux fichiers du moteur ne porte le ``def``. Parité avec ``solar.js batteryKwhFromLines`` (QJR91).
"""
import re

_KWH_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kwh\b", re.IGNORECASE)


def _parse_kwh(nom):
    m = _KWH_RE.search(nom or '')
    return float(m.group(1).replace(',', '.')) if m else None
