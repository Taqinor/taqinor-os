"""Signaux qui déclenchent les webhooks sur les évènements métier (N89).

Évènements couverts :
- lead.created          : à la création d'un Lead.
- lead.lost             : passage du drapeau « perdu » à vrai sur un Lead.
- lead.stage_changed    : changement d'étape pipeline (STAGES.py) d'un Lead.
- devis.sent            : passage d'un Devis au statut « envoyé ».
- devis.accepted        : passage d'un Devis au statut « accepté ».
- facture.created       : à la création d'une Facture.
- facture.paid          : passage d'une Facture au statut « payée ».
- paiement.recorded     : à l'enregistrement d'un paiement sur facture.
- chantier.completed    : passage d'une Installation au statut « clôturé ».
- intervention.completed: passage d'une Intervention au statut « terminée ».
- ticket.created        : à la création d'un Ticket SAV.
- ticket.resolved       : passage d'un Ticket SAV au statut « résolu ».

La détection des transitions se fait en comparant le statut entrant à celui
stocké en base juste avant la sauvegarde. Tout est best-effort : la livraison
(delivery.dispatch_event) attrape ses propres exceptions et ne bloque jamais
la sauvegarde d'origine.

ARC38 — DÉCISION : ``incident_declared`` (QHSE29, désormais aussi sur le bus
``core.events`` — voir docstring de ce module et ``apps/qhse/receivers.py``)
n'a PAS d'équivalent webhook ici et n'en aura pas. Ce module diffuse des
webhooks SORTANTS vers des intégrations CLIENT externes (catalogue fermé
ci-dessus : lead/devis/facture/paiement/chantier/intervention/ticket) ; un
incident QHSE est une donnée INTERNE de sécurité de site, jamais un
événement CLIENT-FACING. Choix documenté, pas d'abonné à ajouter.
"""
import logging

from django.db.models.signals import post_save, pre_save

from apps.crm.models import Lead
from apps.ventes.models import Devis, Facture, Paiement
from apps.installations.models import Installation, Intervention
from apps.sav.models import Ticket

from .constants import (
    EVENT_LEAD_CREATED, EVENT_LEAD_LOST, EVENT_LEAD_STAGE_CHANGED,
    EVENT_DEVIS_SENT, EVENT_DEVIS_ACCEPTED,
    EVENT_FACTURE_CREATED, EVENT_FACTURE_PAID, EVENT_PAIEMENT_RECORDED,
    EVENT_CHANTIER_COMPLETED, EVENT_INTERVENTION_COMPLETED,
    EVENT_TICKET_CREATED, EVENT_TICKET_RESOLVED,
)
from . import delivery

logger = logging.getLogger(__name__)

# Attribut transitoire portant l'ancien statut entre pre_save et post_save.
_OLD_STATUT_ATTR = '_publicapi_old_statut'
# Attributs transitoires propres au Lead (étape + drapeau perdu).
_OLD_STAGE_ATTR = '_publicapi_old_stage'
_OLD_PERDU_ATTR = '_publicapi_old_perdu'


def _capture_old_statut(model, instance):
    """Mémorise sur l'instance le statut actuellement en base (None si neuf)."""
    if not instance.pk:
        setattr(instance, _OLD_STATUT_ATTR, None)
        return
    try:
        old = model.objects.filter(pk=instance.pk).values_list(
            'statut', flat=True).first()
    except Exception:  # noqa: BLE001
        old = None
    setattr(instance, _OLD_STATUT_ATTR, old)


def _safe_dispatch(company_id, event, payload):
    try:
        delivery.dispatch_event(company_id, event, payload)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception('Webhook dispatch failed for %s', event)


# ── Lead ─────────────────────────────────────────────────────────────────────
def lead_pre_save(sender, instance, **kwargs):
    """Mémorise l'étape pipeline + le drapeau perdu d'avant sauvegarde."""
    if not instance.pk:
        setattr(instance, _OLD_STAGE_ATTR, None)
        setattr(instance, _OLD_PERDU_ATTR, None)
        return
    try:
        old = Lead.objects.filter(pk=instance.pk).values_list(
            'stage', 'perdu').first()
    except Exception:  # noqa: BLE001
        old = None
    setattr(instance, _OLD_STAGE_ATTR, old[0] if old else None)
    setattr(instance, _OLD_PERDU_ATTR, old[1] if old else None)


def lead_post_save(sender, instance, created, **kwargs):
    if created:
        _safe_dispatch(instance.company_id, EVENT_LEAD_CREATED, {
            'event': EVENT_LEAD_CREATED,
            'id': instance.pk,
            'nom': instance.nom,
            'email': instance.email,
            'telephone': instance.telephone,
            'stage': instance.stage,
        })
        return
    # Lead perdu : drapeau passé de faux/None à vrai.
    old_perdu = getattr(instance, _OLD_PERDU_ATTR, None)
    if instance.perdu and not old_perdu:
        _safe_dispatch(instance.company_id, EVENT_LEAD_LOST, {
            'event': EVENT_LEAD_LOST,
            'id': instance.pk,
            'nom': instance.nom,
            'stage': instance.stage,
            'motif_perte': instance.motif_perte,
        })
    # Changement d'étape pipeline (STAGES.py).
    old_stage = getattr(instance, _OLD_STAGE_ATTR, None)
    if old_stage is not None and old_stage != instance.stage:
        _safe_dispatch(instance.company_id, EVENT_LEAD_STAGE_CHANGED, {
            'event': EVENT_LEAD_STAGE_CHANGED,
            'id': instance.pk,
            'nom': instance.nom,
            'stage': instance.stage,
            'stage_precedent': old_stage,
        })


# ── Devis ────────────────────────────────────────────────────────────────────
def devis_pre_save(sender, instance, **kwargs):
    _capture_old_statut(Devis, instance)


def devis_post_save(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    if instance.statut == Devis.Statut.ENVOYE and old != Devis.Statut.ENVOYE:
        _safe_dispatch(instance.company_id, EVENT_DEVIS_SENT, {
            'event': EVENT_DEVIS_SENT,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })
    if instance.statut == Devis.Statut.ACCEPTE and old != Devis.Statut.ACCEPTE:
        _safe_dispatch(instance.company_id, EVENT_DEVIS_ACCEPTED, {
            'event': EVENT_DEVIS_ACCEPTED,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })


# ── Installation / Chantier ──────────────────────────────────────────────────
def installation_pre_save(sender, instance, **kwargs):
    _capture_old_statut(Installation, instance)


def installation_post_save(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    done = Installation.Statut.CLOTURE
    if instance.statut == done and old != done:
        _safe_dispatch(instance.company_id, EVENT_CHANTIER_COMPLETED, {
            'event': EVENT_CHANTIER_COMPLETED,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })


# ── Intervention ─────────────────────────────────────────────────────────────
def intervention_pre_save(sender, instance, **kwargs):
    _capture_old_statut(Intervention, instance)


def intervention_post_save(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    done = Intervention.Statut.TERMINEE
    if instance.statut == done and old != done:
        _safe_dispatch(instance.company_id, EVENT_INTERVENTION_COMPLETED, {
            'event': EVENT_INTERVENTION_COMPLETED,
            'id': instance.pk,
            'installation_id': instance.installation_id,
            'statut': instance.statut,
        })


# ── Facture ──────────────────────────────────────────────────────────────────
def facture_pre_save(sender, instance, **kwargs):
    _capture_old_statut(Facture, instance)


def facture_post_save(sender, instance, created, **kwargs):
    if created:
        _safe_dispatch(instance.company_id, EVENT_FACTURE_CREATED, {
            'event': EVENT_FACTURE_CREATED,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    paid = Facture.Statut.PAYEE
    if instance.statut == paid and old != paid:
        _safe_dispatch(instance.company_id, EVENT_FACTURE_PAID, {
            'event': EVENT_FACTURE_PAID,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })


# ── Paiement ─────────────────────────────────────────────────────────────────
def paiement_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    _safe_dispatch(instance.company_id, EVENT_PAIEMENT_RECORDED, {
        'event': EVENT_PAIEMENT_RECORDED,
        'id': instance.pk,
        'facture_id': instance.facture_id,
        'montant': instance.montant,
        'mode': instance.mode,
    })


# ── Ticket SAV ───────────────────────────────────────────────────────────────
def ticket_pre_save(sender, instance, **kwargs):
    _capture_old_statut(Ticket, instance)


def ticket_post_save(sender, instance, created, **kwargs):
    if created:
        _safe_dispatch(instance.company_id, EVENT_TICKET_CREATED, {
            'event': EVENT_TICKET_CREATED,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })
        return
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    resolved = Ticket.Statut.RESOLU
    if instance.statut == resolved and old != resolved:
        _safe_dispatch(instance.company_id, EVENT_TICKET_RESOLVED, {
            'event': EVENT_TICKET_RESOLVED,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })


def connect():
    """Branche tous les récepteurs. Appelé depuis AppConfig.ready()."""
    pre_save.connect(lead_pre_save, sender=Lead,
                     dispatch_uid='publicapi_lead_pre')
    post_save.connect(lead_post_save, sender=Lead,
                      dispatch_uid='publicapi_lead_created')

    pre_save.connect(devis_pre_save, sender=Devis,
                     dispatch_uid='publicapi_devis_pre')
    post_save.connect(devis_post_save, sender=Devis,
                      dispatch_uid='publicapi_devis_accepted')

    pre_save.connect(installation_pre_save, sender=Installation,
                     dispatch_uid='publicapi_chantier_pre')
    post_save.connect(installation_post_save, sender=Installation,
                      dispatch_uid='publicapi_chantier_completed')

    pre_save.connect(intervention_pre_save, sender=Intervention,
                     dispatch_uid='publicapi_intervention_pre')
    post_save.connect(intervention_post_save, sender=Intervention,
                      dispatch_uid='publicapi_intervention_completed')

    pre_save.connect(facture_pre_save, sender=Facture,
                     dispatch_uid='publicapi_facture_pre')
    post_save.connect(facture_post_save, sender=Facture,
                      dispatch_uid='publicapi_facture_paid')

    post_save.connect(paiement_post_save, sender=Paiement,
                      dispatch_uid='publicapi_paiement_recorded')

    pre_save.connect(ticket_pre_save, sender=Ticket,
                     dispatch_uid='publicapi_ticket_pre')
    post_save.connect(ticket_post_save, sender=Ticket,
                      dispatch_uid='publicapi_ticket_created')
