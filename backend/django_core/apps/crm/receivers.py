"""Récepteurs d'événements métier (M6).

Abonne le CRM aux événements du cœur métier exposés par ``core.events``, pour
réagir à des changements d'état déclenchés par d'autres apps (ex. ``ventes``)
sans que celles-ci importent le CRM. Câblé au démarrage par ``CrmConfig.ready``.

ARC37 — s'abonne aussi à ``ticket_resolu`` (``sav`` devient émetteur du bus) :
pose une note chatter ARC8 (``records.services.log_note``) sur le
``crm.Client`` lié au ticket, sans jamais importer ``apps.sav``.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from core.events import (
    appointment_effectue, devis_accepted, devis_refused, devis_sent,
    lead_stage_changed, ticket_resolu,
)

from .models import Appointment, LeadActivity
from .services import (
    _CONTACT_KINDS,
    avancer_stage_new_vers_contacted,
    avancer_stage_pour_devis,
    generer_playbook_progress,
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


@receiver(lead_stage_changed, dispatch_uid="crm_generate_playbook_progress_on_stage_change")
def _generer_playbook_progress_on_stage_change(sender, lead, old_stage,
                                               new_stage, user, **kwargs):
    """NTCRM12 — À CHAQUE changement d'étape d'un lead, génère la progression
    des tâches obligatoires/optionnelles du(des) playbook(s) actif(s) portant
    une étape sur ``new_stage``. Best-effort : ne bloque jamais la transition
    de stage déjà actée par l'émetteur."""
    try:
        generer_playbook_progress(lead, new_stage)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'NTCRM12: génération de la progression playbook échouée '
            'pour le lead #%s', getattr(lead, 'pk', '?'), exc_info=True)


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


# ── PUB30 — appointment_effectue : transition GÉNUINE Appointment → EFFECTUE ──
# Intra-CRM (comme le récepteur QJ7 sur LeadActivity ci-dessus), pas un
# abonnement M6 — CE module ÉMET ici l'événement dont ``adsengine`` (jamais
# importé par crm) s'abonne dans SON PROPRE apps.py/receivers.py, pour pousser
# un événement CAPI dédié (même famille/gating que ADSENG32).

_APPOINTMENT_OLD_STATUT_ATTR = '_pub30_old_statut'


@receiver(pre_save, sender=Appointment,
          dispatch_uid="crm_capture_appointment_old_statut")
def _capture_appointment_old_statut(sender, instance, **kwargs):
    """Capture l'ANCIEN statut (la base porte encore l'ancienne valeur) avant
    le save — un Appointment neuf (pas de pk) → ancien statut None."""
    old = None
    if getattr(instance, 'pk', None):
        old = (Appointment.objects
               .filter(pk=instance.pk)
               .values_list('statut', flat=True)
               .first())
    setattr(instance, _APPOINTMENT_OLD_STATUT_ATTR, old)


@receiver(post_save, sender=Appointment,
          dispatch_uid="crm_emit_appointment_effectue")
def _emit_appointment_effectue_on_transition(sender, instance, created,
                                             **kwargs):
    """Sur une transition GÉNUINE vers EFFECTUE, émet ``appointment_effectue``.

    Un save qui laisse le statut inchangé (ex. édition des notes d'un RDV déjà
    EFFECTUE) ne réémet JAMAIS — même garde que ADSENG32
    (``capi_crm._emit_on_stage_change``). Best-effort : un abonné en échec ne
    casse jamais le save du rendez-vous."""
    new_statut = getattr(instance, 'statut', None)
    if new_statut != Appointment.Statut.EFFECTUE:
        return
    old_statut = getattr(instance, _APPOINTMENT_OLD_STATUT_ATTR, None)
    if not created and old_statut == new_statut:
        return  # save sans changement de statut → rien à émettre.
    try:
        appointment_effectue.send(
            sender='crm.Appointment', appointment=instance,
            company=instance.company, user=None, ancien_statut=old_statut)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'PUB30 : émission appointment_effectue échouée pour le '
            'rendez-vous #%s', getattr(instance, 'pk', '?'), exc_info=True)
