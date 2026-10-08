"""AMOT35 (C-AMOT-045) — UNE règle pour imprimer un bloc « bancable »
(P50/P90 de ``etude_params['simulation']``).

Une P50/P90 n'est imprimée que si la simulation décrit le champ VENDU
(Σ kWc des zones simulées = kWc du devis à ``TOLERANCE_KWC_SIMULATION``
près) et reste cohérente avec la production imprimée sur la même page (P50 à
``TOLERANCE_PRODUCTION_PAGE`` près). Pure, stdlib seulement : appelée par le
moteur legacy ET par la page finance industrielle (et, côté page publique,
``public_views._bankable_headline`` devrait l'appeler aussi — cité).
"""

#: QJR159 (b) — écart RELATIF toléré entre la puissance simulée et la
#: puissance VENDUE (2 % absorbe les arrondis kWc/panneaux, jamais un vrai
#: changement de taille).
TOLERANCE_KWC_SIMULATION = 0.02

#: QJR115 — écart RELATIF toléré entre la P50 et la production imprimée sur
#: la même page (la tolérance de la garde QJR114 côté moteur).
TOLERANCE_PRODUCTION_PAGE = 0.01

MOTIF_CHAMP = ("bloc bancable omis : la simulation ne décrit pas le champ "
               "vendu (kWc simulés ≠ kWc du devis)")
MOTIF_PRODUCTION = ("bloc bancable omis : la P50 de la simulation contredit "
                    "la production imprimée")


def _f(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def decrit_le_champ(bank, kwc_devis):
    """Σ ``kwc`` des zones simulées = ``kwc_devis`` (± 2 %). Tout ce qui
    n'est pas prouvé (kWc inconnu, zones absentes/illisibles) rend False."""
    if not isinstance(bank, dict):
        return False
    kwc = _f(kwc_devis)
    if not kwc or kwc <= 0:
        return False
    zones = bank.get("zones")
    if not isinstance(zones, (list, tuple)) or not zones:
        return False
    total = 0.0
    for zone in zones:
        if not isinstance(zone, dict):
            return False
        v = _f(zone.get("kwc"))
        if v is None:
            return False
        total += v
    if total <= 0:
        return False
    return abs(total - kwc) <= kwc * TOLERANCE_KWC_SIMULATION


def concorde_avec_production(bank, production_servie):
    """La P50 dit la MÊME production que la page (± 1 %). True quand il n'y
    a rien à contredire (pas de production imprimée, pas de P50) ; False dès
    qu'un des deux nombres est illisible."""
    if production_servie in (None, ""):
        return True
    pr = bank.get("pr") if isinstance(bank, dict) else None
    p50 = pr.get("p50_kwh") if isinstance(pr, dict) else None
    if p50 in (None, ""):
        return True
    prod, p50 = _f(production_servie), _f(p50)
    if prod is None or p50 is None or prod <= 0:
        return False
    return abs(p50 - prod) <= prod * TOLERANCE_PRODUCTION_PAGE


def bankable_imprimable(bank, kwc_devis, production_servie):
    """``(imprimable, motif)`` — ``motif`` (texte interne) quand le bloc doit
    être omis, ``None`` sinon."""
    if not decrit_le_champ(bank, kwc_devis):
        return False, MOTIF_CHAMP
    if not concorde_avec_production(bank, production_servie):
        return False, MOTIF_PRODUCTION
    return True, None
