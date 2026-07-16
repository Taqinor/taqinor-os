"""Services (écriture/orchestration) du module Hôtellerie & restauration."""
from .models import PlanTarifaire


# ── NTHOT2 — Tarification saisonnière (rack/corporate/ota) ─────────────────

# Priorité par défaut quand aucun canal n'est explicitement demandé (ou que le
# canal demandé n'a pas de plan pour la date) : corporate > ota > rack.
_CANAL_PRIORITE_DEFAUT = [
    PlanTarifaire.Canal.CORPORATE,
    PlanTarifaire.Canal.OTA,
    PlanTarifaire.Canal.RACK,
]


def prix_applicable(type_chambre, date, canal=None):
    """Résout le prix/nuit HT applicable à ``type_chambre`` pour ``date``.

    Plusieurs plans peuvent se chevaucher — jamais ambigu :
    1. si ``canal`` est fourni, un plan EXPLICITE pour ce canal à cette date
       est prioritaire ;
    2. sinon (ou si aucun plan pour ce canal), priorité par défaut
       corporate > ota > rack ;
    3. une date sans plan spécifique retombe naturellement sur le tarif rack
       (un plan rack à large plage de dates joue le rôle de tarif par défaut).

    Renvoie ``None`` si aucun plan ne couvre la date (aucun tarif configuré).
    """
    candidats = PlanTarifaire.objects.filter(
        type_chambre=type_chambre, date_debut__lte=date, date_fin__gte=date)

    if canal:
        exact = candidats.filter(canal=canal).order_by('-date_debut').first()
        if exact is not None:
            return exact.prix_nuit_ht

    for c in _CANAL_PRIORITE_DEFAUT:
        plan = candidats.filter(canal=c).order_by('-date_debut').first()
        if plan is not None:
            return plan.prix_nuit_ht

    return None
