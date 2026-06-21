"""Récepteurs d'événements métier (M6).

Abonne le CRM aux événements du cœur métier exposés par ``core.events``, pour
réagir à des changements d'état déclenchés par d'autres apps (ex. ``ventes``)
sans que celles-ci importent le CRM. Câblé au démarrage par ``CrmConfig.ready``.
"""
from django.dispatch import receiver

from core.events import devis_accepted, devis_refused

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


@receiver(devis_refused, dispatch_uid="crm_mark_lead_perdu_on_devis_refused")
def _marquer_lead_perdu_on_devis_refused(sender, devis, user, motif_refus,
                                         **kwargs):
    """FG44 — au refus d'un devis (optionnel), marque le lead perdu (perdu=True).

    Ne s'active que si le devis a un lead associé et que ``marquer_lead_perdu``
    est True dans les kwargs (la vue envoie ce paramètre si l'utilisateur a coché
    la case). Le motif de refus du devis devient le motif_perte du lead.
    """
    if not getattr(devis, 'lead_id', None):
        return
    marquer = kwargs.get('marquer_lead_perdu', False)
    if not marquer:
        return
    # Import local pour éviter les cycles (CRM n'importe pas ventes.models).
    from .models import Lead
    try:
        lead = Lead.objects.get(pk=devis.lead_id, company=devis.company)
    except Lead.DoesNotExist:
        return
    if lead.perdu:
        return  # Déjà perdu, ne pas écraser.
    from . import activity as crm_activity
    old_perdu = lead.perdu
    old_motif = lead.motif_perte
    lead.perdu = True
    lead.motif_perte = (motif_refus or '')[:255] or None
    lead.save(update_fields=['perdu', 'motif_perte'])
    crm_activity.log_bulk_change(lead, user, 'perdu', old_perdu, True)
    if motif_refus:
        crm_activity.log_bulk_change(lead, user, 'motif_perte',
                                     old_motif, motif_refus)
