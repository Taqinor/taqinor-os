"""Récepteurs d'événements métier (M6).

Abonne le CRM aux événements du cœur métier exposés par ``core.events``, pour
réagir à des changements d'état déclenchés par d'autres apps (ex. ``ventes``)
sans que celles-ci importent le CRM. Câblé au démarrage par ``CrmConfig.ready``.

ARC37 — s'abonne aussi à ``ticket_resolu`` (``sav`` devient émetteur du bus) :
pose une note chatter ARC8 (``records.services.log_note``) sur le
``crm.Client`` lié au ticket, sans jamais importer ``apps.sav``.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.events import devis_accepted, devis_refused, devis_sent, ticket_resolu

from .models import LeadActivity
from .services import (
    _CONTACT_KINDS,
    avancer_stage_new_vers_contacted,
    avancer_stage_pour_devis,
    signaler_mismatch_signe_sur_refus,
)

logger = logging.getLogger(__name__)


@receiver(devis_accepted, dispatch_uid="crm_advance_stage_on_devis_accepted")
def _avancer_stage_on_devis_accepted(sender, devis, user, ancien_statut,
                                     **kwargs):
    """À l'acceptation d'un devis, avance l'étape du lead (→ SIGNED).

    Remplace, à l'identique, l'appel direct ``ventes → crm.services`` qui était
    fait au site d'acceptation : même règle (ne recule jamais, ignore les leads
    perdus), désormais déclenchée par l'événement ``devis_accepted``.
    """
    avancer_stage_pour_devis(devis, ancien_statut, devis.statut, user)


@receiver(devis_sent, dispatch_uid="crm_advance_stage_on_devis_sent")
def _avancer_stage_on_devis_sent(sender, devis, user, ancien_statut,
                                 **kwargs):
    """À l'ENVOI d'un devis (U4), avance l'étape du lead (→ QUOTE_SENT).

    Même câblage que ``devis_accepted`` : ``avancer_stage_pour_devis`` ne recule
    jamais le funnel et ignore les leads perdus, donc l'avance vers QUOTE_SENT
    est sûre et idempotente (un lead déjà ≥ QUOTE_SENT ne bouge pas).
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


@receiver(devis_accepted, dispatch_uid="crm_flip_parrainage_converti_on_devis_accepted")
def _flip_parrainage_converti_on_devis_accepted(sender, devis, user, ancien_statut,
                                                **kwargs):
    """QX35 — Quand le devis d'un FILLEUL est accepté, le parrainage passe
    ``en_attente`` → ``converti`` (la récompense reste versée manuellement,
    hors périmètre ici). Même bus que l'avance de funnel ci-dessus — aucun
    import de ``ventes`` (le devis n'est manipulé qu'au travers des kwargs du
    signal). No-op si le devis n'a pas de lead, si aucun Parrainage
    ``en_attente`` ne le référence, ou s'il est déjà ``converti``/
    ``recompense_versee`` (jamais reculé)."""
    if not getattr(devis, 'lead_id', None):
        return
    from .models import Parrainage
    parrainage = Parrainage.objects.filter(
        filleul_lead_id=devis.lead_id, company=devis.company,
        statut=Parrainage.Statut.EN_ATTENTE,
    ).first()
    if parrainage is None:
        return
    parrainage.statut = Parrainage.Statut.CONVERTI
    parrainage.save(update_fields=['statut'])


@receiver(devis_refused, dispatch_uid="crm_signal_signe_sans_devis_actif")
def _signaler_signe_sans_devis_actif(sender, devis, user, motif_refus,
                                     **kwargs):
    """U11 — au refus d'un devis, signale (sans reculer l'étape) si le lead reste
    coincé à SIGNED sans aucun devis accepté actif (« signé fantôme »).

    Indépendant de la case « marquer le lead perdu » : la cohérence du funnel
    doit être signalée que l'utilisateur coche ou non cette case. Conforme à la
    règle #2 (le funnel est une couche permanente, séparée des statuts DOCUMENT —
    on NE recule JAMAIS l'étape à l'aveugle).
    """
    if not getattr(devis, 'lead_id', None):
        return
    signaler_mismatch_signe_sur_refus(devis, user)


# ── QJ7 — Avance automatique NEW → CONTACTED au premier contact ──────────────

@receiver(post_save, sender=LeadActivity,
          dispatch_uid="crm_advance_stage_new_vers_contacted_on_activity")
def _avancer_stage_on_contact_activity(sender, instance, created, **kwargs):
    """QJ7 — Quand la PREMIÈRE activité de contact (NOTE/APPEL/EMAIL) est créée
    sur un lead NEW (et non perdu), avance l'étape vers CONTACTED — une seule fois.

    Intra-CRM : utilise ``post_save`` sur ``LeadActivity`` (pas de bus cross-app).
    Le garde-fou « ne recule jamais » et « ignore les leads perdus » est délégué à
    ``avancer_stage_new_vers_contacted`` dans ``services.py``.
    """
    if not created:
        return  # mise à jour, pas une nouvelle activité
    if instance.kind not in _CONTACT_KINDS:
        return  # CREATION ou MODIFICATION ne déclenchent pas l'avancée
    if instance.user is None:
        return  # uniquement un contact MANUEL d'un utilisateur (pas auto/système)
    lead = instance.lead
    avancer_stage_new_vers_contacted(lead, instance.user)


@receiver(ticket_resolu, dispatch_uid="crm_chatter_on_ticket_resolu")
def _chatter_on_ticket_resolu(sender, ticket, company, user, ancien_statut,
                              **kwargs):
    """ARC37 — à la résolution d'un ticket SAV, pose une note chatter ARC8 sur
    le ``crm.Client`` lié (``sav.Ticket.client`` — lien direct, jamais un
    import d'``apps.sav.models``, uniquement l'instance déjà portée par le
    signal). Best-effort : une erreur ici ne doit jamais remonter (la
    résolution, côté ``sav``, est déjà actée)."""
    client = getattr(ticket, 'client', None)
    if client is None:
        return
    try:
        from apps.records.services import log_note

        log_note(
            client, user,
            f'Ticket SAV {ticket.reference} résolu.',
            company=company)
    except Exception:  # noqa: BLE001 — best-effort, ne casse jamais
        logger.warning(
            'ARC37 : chatter ARC8 échoué sur ticket_resolu pour ticket #%s',
            getattr(ticket, 'pk', '?'), exc_info=True)
