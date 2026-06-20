"""Producteurs d'évènements pour le moteur de notifications (ERR50).

Avant : ``notify()`` n'était appelé que par les digests planifiés et les tests —
le moteur était inerte pour les évènements métier. On câble ici les producteurs
DEPUIS l'app notifications (en miroir de ``apps/publicapi/signals.py``), sans
jamais éditer crm/ventes : on connecte simplement des récepteurs à leurs
``pre_save``/``post_save``.

Producteurs câblés :
- ``LEAD_ASSIGNED``  : quand le ``owner`` d'un Lead passe à un utilisateur
  (création avec owner, ou réassignation).
- ``DEVIS_ACCEPTED`` : quand un Devis passe au statut « accepté » (transition).

Tout est best-effort : ``notify()`` isole déjà ses propres exceptions, et les
récepteurs en rajoutent une couche pour ne JAMAIS bloquer le save d'origine.

``FACTURE_OVERDUE`` est temporel (pas une transition de save) ; il devra être
émis depuis le job planifié qui détecte les échéances dépassées — laissé en
suivi explicite, hors de ce câblage par signaux.
"""
import logging

from django.db.models.signals import post_save, pre_save

from .models import EventType
from .services import notify

logger = logging.getLogger(__name__)

_OLD_OWNER_ATTR = '_notif_old_owner_id'
_OLD_STATUT_ATTR = '_notif_old_statut'


# ── Lead → LEAD_ASSIGNED ─────────────────────────────────────────────────────
def lead_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'owner_id', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_OWNER_ATTR, old)


def lead_post_save(sender, instance, created, **kwargs):
    old_owner = getattr(instance, _OLD_OWNER_ATTR, None)
    new_owner = instance.owner_id
    if not new_owner or new_owner == old_owner:
        return
    try:
        ville = getattr(instance, 'ville', '') or ''
        notify(
            user=instance.owner,
            event_type=EventType.LEAD_ASSIGNED,
            title='Nouveau lead assigné',
            body=(instance.nom or '') + (f' — {ville}' if ville else ''),
            link=f'/leads/{instance.pk}',
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception('notify LEAD_ASSIGNED failed (lead %s)', instance.pk)


# ── Devis → DEVIS_ACCEPTED ───────────────────────────────────────────────────
def devis_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'statut', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_STATUT_ATTR, old)


def devis_post_save(sender, instance, created, **kwargs):
    from apps.ventes.models import Devis
    old = getattr(instance, _OLD_STATUT_ATTR, None)
    if instance.statut != Devis.Statut.ACCEPTE or old == Devis.Statut.ACCEPTE:
        return
    recipient = getattr(instance, 'created_by', None)
    if recipient is None:
        return
    try:
        notify(
            user=recipient,
            event_type=EventType.DEVIS_ACCEPTED,
            title='Devis accepté',
            body=f'Le devis {instance.reference} a été accepté.',
            link=f'/devis/{instance.pk}',
        )
    except Exception:  # noqa: BLE001
        logger.exception('notify DEVIS_ACCEPTED failed (devis %s)', instance.pk)


def connect():
    """Branche les récepteurs. Appelé depuis ``AppConfig.ready()``."""
    from apps.crm.models import Lead
    from apps.ventes.models import Devis

    pre_save.connect(lead_pre_save, sender=Lead,
                     dispatch_uid='notifications_lead_pre')
    post_save.connect(lead_post_save, sender=Lead,
                      dispatch_uid='notifications_lead_assigned')
    pre_save.connect(devis_pre_save, sender=Devis,
                     dispatch_uid='notifications_devis_pre')
    post_save.connect(devis_post_save, sender=Devis,
                      dispatch_uid='notifications_devis_accepted')
