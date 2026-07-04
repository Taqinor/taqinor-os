"""Producteurs d'évènements pour le moteur de notifications (ERR50).

Avant : ``notify()`` n'était appelé que par les digests planifiés et les tests —
le moteur était inerte pour les évènements métier. On câble ici les producteurs
DEPUIS l'app notifications (en miroir de ``apps/publicapi/signals.py``), sans
jamais éditer crm/ventes/sav/automation/compta : on connecte simplement des
récepteurs à leurs ``pre_save``/``post_save``.

Producteurs câblés :
- ``LEAD_ASSIGNED``    : quand le ``owner`` d'un Lead passe à un utilisateur
  (création avec owner, ou réassignation).
- ``DEVIS_ACCEPTED``   : quand un Devis passe au statut « accepté » (transition).
- ``SAV_TICKET_OPENED`` (YEVNT4) : à la CRÉATION d'un ``sav.Ticket``.
- ``APPROVAL_REQUESTED``/``APPROVAL_DECIDED`` (YEVNT8) : sur
  ``automation.AutomationApproval`` (création → approbateur ; décision →
  demandeur) ET ``compta.DemandeApprobationConfig`` (même paire).

Tout est best-effort : ``notify()`` isole déjà ses propres exceptions, et les
récepteurs en rajoutent une couche pour ne JAMAIS bloquer le save d'origine.

``FACTURE_OVERDUE`` est temporel (pas une transition de save) ; il est émis par
le balayage quotidien (``sweeps.py``), pas par un signal de save.
"""
import logging

from django.db.models.signals import post_save, pre_save

from .models import EventType
from .services import notify

logger = logging.getLogger(__name__)

_OLD_OWNER_ATTR = '_notif_old_owner_id'
_OLD_STATUT_ATTR = '_notif_old_statut'
_OLD_DEMANDE_STATUT_ATTR = '_notif_old_demande_statut'


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


# ── Devis → DEVIS_EXPIRED (YEVNT2) ──────────────────────────────────────────
# Contrairement aux autres producteurs de ce module (qui diffent pre/post_save
# sur le modèle), YEVNT2 s'abonne DIRECTEMENT à ``core.events.devis_expired`` —
# le signal domain-event posé par ``ventes.services.expire_stale_devis``
# (M6) : plus simple ici (le sweep ne pose l'événement QU'à la transition
# réelle envoyé→expiré, donc aucune diffing pre/post_save n'est nécessaire).
def devis_expired_receiver(sender, devis, ancien_statut, **kwargs):
    recipient = getattr(devis, 'created_by', None)
    if recipient is None:
        return
    try:
        notify(
            user=recipient,
            event_type=EventType.DEVIS_EXPIRED,
            title='Devis expiré',
            body=(f'Le devis {devis.reference} a expiré automatiquement '
                  '(date de validité dépassée). Pensez à relancer le client.'),
            link=f'/devis/{devis.pk}',
        )
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception('notify DEVIS_EXPIRED failed (devis %s)', devis.pk)


# ── SAV Ticket → SAV_TICKET_OPENED (YEVNT4) ─────────────────────────────────
def sav_ticket_post_save(sender, instance, created, **kwargs):
    """À la CRÉATION d'un ticket SAV → notifie le technicien assigné, sinon
    les managers de la société. Best-effort, ne casse jamais la création."""
    if not created:
        return
    try:
        from .sweeps import _notify_user_or_managers
        company = getattr(instance, 'company', None)
        technicien = getattr(instance, 'technicien_responsable', None)
        client_nom = ''
        try:
            client_nom = getattr(instance.client, 'nom', '') or ''
        except Exception:  # noqa: BLE001
            client_nom = ''
        title = 'Ticket SAV ouvert'
        body = (
            f"Le ticket SAV « {instance.reference} » "
            + (f'({client_nom}) ' if client_nom else '')
            + f'a été ouvert (priorité : {instance.get_priorite_display()}).'
        )
        link = f'/sav/tickets/{instance.pk}'
        # `_notify_user_or_managers` retombe déjà sur les managers si
        # `technicien` est None — un seul appel couvre les deux cas.
        _notify_user_or_managers(
            technicien, company, EventType.SAV_TICKET_OPENED, title, body, link)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify SAV_TICKET_OPENED failed (ticket %s)', instance.pk)


# ── automation.AutomationApproval → APPROVAL_REQUESTED / APPROVAL_DECIDED ───
# (YEVNT8)

def automation_approval_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'status', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_STATUT_ATTR, old)


def automation_approval_post_save(sender, instance, created, **kwargs):
    from apps.automation.models import AutomationApproval
    try:
        from .sweeps import _managers
        company = instance.company
        link = f'/automation/approvals/{instance.pk}'
        if created:
            title = "Approbation demandée"
            body = instance.description or 'Une action attend votre approbation.'
            for approver in _managers(company):
                notify(
                    approver, EventType.APPROVAL_REQUESTED, title, body=body,
                    link=link, company=company)
            return

        old = getattr(instance, _OLD_STATUT_ATTR, None)
        if instance.status == old or instance.status == AutomationApproval.Status.PENDING:
            return  # pas une décision (toujours en attente, ou pas de transition).
        requester = getattr(instance, 'requested_by', None)
        if requester is None:
            return
        decided_label = (
            'approuvée' if instance.status == AutomationApproval.Status.APPROVED
            else 'rejetée')
        body = f'{instance.description or "Votre demande"} a été {decided_label}.'
        notify(
            requester, EventType.APPROVAL_DECIDED, 'Approbation décidée',
            body=body, link=link, company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify APPROVAL_* failed (automation approval %s)', instance.pk)


# ── compta.DemandeApprobationConfig → APPROVAL_REQUESTED / APPROVAL_DECIDED ─
# (YEVNT8)

def demande_approbation_pre_save(sender, instance, **kwargs):
    old = None
    if instance.pk:
        try:
            old = sender.objects.filter(pk=instance.pk).values_list(
                'statut', flat=True).first()
        except Exception:  # noqa: BLE001
            old = None
    setattr(instance, _OLD_DEMANDE_STATUT_ATTR, old)


def demande_approbation_post_save(sender, instance, created, **kwargs):
    from apps.compta.models import DemandeApprobationConfig
    try:
        from .sweeps import _managers
        company = instance.company
        link = f'/compta/approbations/{instance.pk}'
        label = instance.devis_reference or instance.devis_id or ''
        if created:
            title = "Approbation demandée"
            body = f'Composition non-standard à valider ({label}) : {instance.motif}'
            for approver in _managers(company):
                notify(
                    approver, EventType.APPROVAL_REQUESTED, title, body=body,
                    link=link, company=company)
            return

        old = getattr(instance, _OLD_DEMANDE_STATUT_ATTR, None)
        if (instance.statut == old
                or instance.statut == DemandeApprobationConfig.Statut.EN_ATTENTE):
            return  # pas une décision.
        requester = getattr(instance, 'demandeur', None)
        if requester is None:
            return
        decided_label = (
            'approuvée'
            if instance.statut == DemandeApprobationConfig.Statut.APPROUVEE
            else 'refusée')
        body = f'Votre demande ({label}) a été {decided_label}.'
        if instance.commentaire_decision:
            body += f' Motif : {instance.commentaire_decision}'
        notify(
            requester, EventType.APPROVAL_DECIDED, 'Approbation décidée',
            body=body, link=link, company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.exception(
            'notify APPROVAL_* failed (demande approbation %s)', instance.pk)


def connect():
    """Branche les récepteurs. Appelé depuis ``AppConfig.ready()``."""
    from apps.automation.models import AutomationApproval
    from apps.compta.models import DemandeApprobationConfig
    from apps.crm.models import Lead
    from apps.sav.models import Ticket
    from apps.ventes.models import Devis
    from core.events import devis_expired

    pre_save.connect(lead_pre_save, sender=Lead,
                     dispatch_uid='notifications_lead_pre')
    post_save.connect(lead_post_save, sender=Lead,
                      dispatch_uid='notifications_lead_assigned')
    pre_save.connect(devis_pre_save, sender=Devis,
                     dispatch_uid='notifications_devis_pre')
    post_save.connect(devis_post_save, sender=Devis,
                      dispatch_uid='notifications_devis_accepted')
    devis_expired.connect(devis_expired_receiver,
                          dispatch_uid='notifications_devis_expired')
    post_save.connect(sav_ticket_post_save, sender=Ticket,
                      dispatch_uid='notifications_sav_ticket_opened')
    pre_save.connect(automation_approval_pre_save, sender=AutomationApproval,
                     dispatch_uid='notifications_automation_approval_pre')
    post_save.connect(
        automation_approval_post_save, sender=AutomationApproval,
        dispatch_uid='notifications_automation_approval_events')
    pre_save.connect(
        demande_approbation_pre_save, sender=DemandeApprobationConfig,
        dispatch_uid='notifications_demande_approbation_pre')
    post_save.connect(
        demande_approbation_post_save, sender=DemandeApprobationConfig,
        dispatch_uid='notifications_demande_approbation_events')
