"""Signaux qui déclenchent les webhooks sur les évènements métier (N89).

Évènements couverts :
- lead.created       : à la création d'un Lead.
- devis.accepted     : passage d'un Devis au statut « accepté ».
- chantier.completed : passage d'une Installation au statut « clôturé ».
- facture.paid       : passage d'une Facture au statut « payée ».

La détection des transitions se fait en comparant le statut entrant à celui
stocké en base juste avant la sauvegarde. Tout est best-effort : la livraison
(delivery.dispatch_event) attrape ses propres exceptions et ne bloque jamais
la sauvegarde d'origine.
"""
import logging

from django.db.models.signals import post_save, pre_save

from apps.crm.models import Lead
from apps.ventes.models import Devis, Facture
from apps.installations.models import Installation

from .constants import (
    EVENT_LEAD_CREATED, EVENT_DEVIS_ACCEPTED,
    EVENT_CHANTIER_COMPLETED, EVENT_FACTURE_PAID,
)
from . import delivery

logger = logging.getLogger(__name__)

# Attribut transitoire portant l'ancien statut entre pre_save et post_save.
_OLD_STATUT_ATTR = '_publicapi_old_statut'


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
def lead_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    _safe_dispatch(instance.company_id, EVENT_LEAD_CREATED, {
        'event': EVENT_LEAD_CREATED,
        'id': instance.pk,
        'nom': instance.nom,
        'email': instance.email,
        'telephone': instance.telephone,
        'stage': instance.stage,
    })


# ── Devis ────────────────────────────────────────────────────────────────────
def devis_pre_save(sender, instance, **kwargs):
    _capture_old_statut(Devis, instance)


def devis_post_save(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD_STATUT_ATTR, None)
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


# ── Facture ──────────────────────────────────────────────────────────────────
def facture_pre_save(sender, instance, **kwargs):
    _capture_old_statut(Facture, instance)


def facture_post_save(sender, instance, created, **kwargs):
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    paid = Facture.Statut.PAYEE
    if instance.statut == paid and old != paid:
        _safe_dispatch(instance.company_id, EVENT_FACTURE_PAID, {
            'event': EVENT_FACTURE_PAID,
            'id': instance.pk,
            'reference': instance.reference,
            'statut': instance.statut,
        })


def connect():
    """Branche tous les récepteurs. Appelé depuis AppConfig.ready()."""
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

    pre_save.connect(facture_pre_save, sender=Facture,
                     dispatch_uid='publicapi_facture_pre')
    post_save.connect(facture_post_save, sender=Facture,
                      dispatch_uid='publicapi_facture_paid')
