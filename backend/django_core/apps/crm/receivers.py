"""Récepteurs d'événements métier (M6).

Abonne le CRM aux événements du cœur métier exposés par ``core.events``, pour
réagir à des changements d'état déclenchés par d'autres apps (ex. ``ventes``)
sans que celles-ci importent le CRM. Câblé au démarrage par ``CrmConfig.ready``.
"""
from django.dispatch import receiver

from core.events import devis_accepted

from .services import avancer_stage_pour_devis


@receiver(devis_accepted, dispatch_uid="crm_advance_stage_on_devis_accepted")
def _avancer_stage_on_devis_accepted(sender, devis, user, ancien_statut,
                                     **kwargs):
    """À l'acceptation d'un devis, avance l'étape du lead (→ SIGNED).

    Remplace, à l'identique, l'appel direct ``ventes → crm.services`` qui était
    fait au site d'acceptation : même règle (ne recule jamais, ignore les leads
    perdus), désormais déclenchée par l'événement ``devis_accepted``.
    """
    avancer_stage_pour_devis(devis, ancien_statut, devis.statut, user)
