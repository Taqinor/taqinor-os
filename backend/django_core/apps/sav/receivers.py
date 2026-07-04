"""Récepteurs d'événements métier (M6) — YSUBS5.

Abonne ``sav`` aux événements du cœur métier exposés par ``core.events``, pour
réagir à la résiliation d'un contrat (``apps.contrats``) SANS que ``contrats``
importe ``sav`` ni l'inverse. Câblé au démarrage par ``SavConfig.ready``.
"""
import logging

from django.dispatch import receiver

from core.events import contrat_resilie

logger = logging.getLogger(__name__)


@receiver(contrat_resilie, dispatch_uid="sav_deprovision_on_contrat_resilie")
def _deprovisionner_maintenance_on_contrat_resilie(
        sender, contrat_id, company, date_effet, **kwargs):
    """YSUBS5 — à la résiliation d'un contrat, stoppe la facturation
    récurrente et les visites préventives futures du ``ContratMaintenance``
    lié (résolu via ``contrats.selectors.contrat_id_maintenance_lie`` —
    JAMAIS un import du modèle ``contrats``, frontière cross-app).

    Un contrat sans maintenance liée ne déclenche RIEN (no-op silencieux) —
    la très grande majorité des contrats (vente, PPA, garantie...) n'a pas
    de ``ContratMaintenance`` associé. Best-effort : une erreur ne doit
    jamais remonter (la résiliation, côté ``contrats``, est déjà actée)."""
    try:
        from apps.contrats.selectors import contrat_maintenance_lie_id

        maintenance_id = contrat_maintenance_lie_id(company, contrat_id)
        if not maintenance_id:
            return

        from .models import ContratMaintenance

        ContratMaintenance.objects.filter(
            id=maintenance_id, company=company,
        ).update(actif=False, facturation_active=False)
    except Exception:  # pragma: no cover - défensif (best-effort)
        logger.warning(
            'sav: échec de-provisioning maintenance sur résiliation du '
            'contrat #%s', contrat_id, exc_info=True)
