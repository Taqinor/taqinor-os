"""AMOT35 (C-AMOT-045) — LA règle « une P50/P90 bancable est-elle
imprimable ? », UNE fonction pure partagée par le moteur legacy (page Étude)
et la page finance industrielle.

Le builder recopie ``etude_params['simulation']`` sans condition dans
``etude['bankable']`` : une simulation jouée avant un redimensionnement (ou
sur un autre champ PV) imprimait une P90 qui contredisait la production du
document — « P90 : 987 654 kWh/an » sur un devis industriel de 49,7 kWc et
79 482 kWh. La P50/P90 n'est imprimée que si :

1. la simulation décrit le champ VENDU : Σ ``zones[].kwc`` = kWc du devis à
   :data:`TOLERANCE_KWC_SIMULATION` près ;
2. sa P50 dit la même production que celle imprimée : écart ≤
   :data:`TOLERANCE_PRODUCTION_PAGE` (rien à contredire quand le document
   n'imprime pas de production, ou que le bloc n'a pas de P50).

Stdlib seulement, aucun global de rendu : importable par le legacy comme par
les paquets premium.
"""

#: QJR159 (b) — écart RELATIF toléré entre la puissance simulée et la
#: puissance VENDUE (2 % absorbe les arrondis kWc/panneaux).
TOLERANCE_KWC_SIMULATION = 0.02

#: QJR115 — écart RELATIF toléré entre la P50 et la production imprimée.
TOLERANCE_PRODUCTION_PAGE = 0.01


def _nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def decrit_le_champ(bank, kwc_devis):
    """La simulation décrit-elle le champ PV vendu (``kwc_devis``) ?"""
    if not isinstance(bank, dict):
        return False
    kwc = _nombre(kwc_devis)
    if not kwc or kwc <= 0:
        return False
    zones = bank.get("zones")
    if not isinstance(zones, (list, tuple)) or not zones:
        return False
    total = 0.0
    for zone in zones:
        if not isinstance(zone, dict):
            return False
        v = _nombre(zone.get("kwc"))
        if v is None:
            return False
        total += v
    if total <= 0:
        return False
    return abs(total - kwc) <= kwc * TOLERANCE_KWC_SIMULATION


def concorde_avec_la_production(bank, production_servie):
    """La P50 dit-elle la même production que celle imprimée ?"""
    if production_servie in (None, ""):
        return True
    pr = bank.get("pr") if isinstance(bank, dict) else None
    p50 = pr.get("p50_kwh") if isinstance(pr, dict) else None
    if p50 in (None, ""):
        return True
    prod = _nombre(production_servie)
    p50 = _nombre(p50)
    if prod is None or p50 is None or prod <= 0:
        return False
    return abs(p50 - prod) <= prod * TOLERANCE_PRODUCTION_PAGE


def bankable_imprimable(bank, kwc_devis, production_servie):
    """``(imprimable, motif)`` — ``motif`` (français, pour
    ``avertissements_internes``) est ``None`` quand le bloc est imprimable."""
    if not isinstance(bank, dict) or not bank:
        return False, "aucune simulation bancable"
    if not decrit_le_champ(bank, kwc_devis):
        return False, ("simulation bancable périmée : elle ne décrit pas le "
                       "champ PV vendu — P50/P90 omises")
    if not concorde_avec_la_production(bank, production_servie):
        return False, ("simulation bancable incohérente avec la production "
                       "imprimée — P50/P90 omises")
    return True, None
