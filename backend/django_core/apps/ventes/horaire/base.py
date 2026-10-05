"""Helpers feuilles du moteur horaire (SPL254, déplacé de ``etude_horaire.py``).

Mois d'été des factures, saison PVGIS d'un mois, flottant tolérant ``_num`` —
les feuilles que les autres modules de ``horaire/`` lisent sans importer
``etude_horaire`` en retour (sens unique, pas de cycle). Déplacement pur :
corps octet-identiques, prouvé par ``tests/golden/split_eh_base.json``.
"""
from apps.parametres.pvgis_profils import MOIS_PAR_SAISON


#: Mois (index 0 = janvier) considérés « été » quand le lead déclare une
#: facture d'été DISTINCTE. Mai→octobre — MÊME découpage que
#: ``apps/ventes/public_views._monthly_consumption``, qui sert déjà la série
#: mensuelle de la page : deux découpages différents feraient diverger l'écran
#: et le moteur sur le même client.
MOIS_ETE_FACTURE = frozenset({4, 5, 6, 7, 8, 9})


#: Mois (1-12) → saison PVGIS, dérivé de ``MOIS_PAR_SAISON`` (source unique :
#: hiver = DJF, mi-saison = MAM+SON, été = JJA). Jamais un second découpage.
_SAISON_DU_MOIS = {
    mois: saison
    for saison, mois_tuple in MOIS_PAR_SAISON.items()
    for mois in mois_tuple
}


def _num(valeur, defaut=0.0):
    """Flottant tolérant — illisible/``None`` → ``defaut``, jamais d'exception."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return float(defaut)


def saison_du_mois(mois):
    """Saison PVGIS d'un mois 1-12 (``None`` hors bornes)."""
    return _SAISON_DU_MOIS.get(mois)
