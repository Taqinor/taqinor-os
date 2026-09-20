"""NTOBS15 — notifie les abonnés confirmés à l'ouverture/résolution d'un
incident public de LEUR région (filtre vide = toutes régions).

Envoi via ``django.core.mail`` directement (même patron que
``apps.sav.services`` : sans ``SENDGRID_API_KEY``/backend réel configuré,
Django retombe sur le backend console — NO-OP réseau silencieux,
``fail_silently=True``). Uniquement les incidents SYSTÈME (``company=None``)
— jamais un incident société-spécifique envoyé à des abonnés publics
anonymes.
"""
import logging

from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import IncidentPublic, StatusSubscriber

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=IncidentPublic)
def _capturer_ancien_statut(sender, instance, **kwargs):
    """Mémorise le statut AVANT sauvegarde sur l'instance elle-même (lu par
    le ``post_save`` ci-dessous pour détecter une transition -> résolu)."""
    if instance.pk:
        try:
            instance._ancien_statut = (
                IncidentPublic.objects.only('statut').get(pk=instance.pk).statut)
        except IncidentPublic.DoesNotExist:
            instance._ancien_statut = None
    else:
        instance._ancien_statut = None


@receiver(post_save, sender=IncidentPublic)
def _notifier_abonnes_incident(sender, instance, created, **kwargs):
    ancien = getattr(instance, '_ancien_statut', None)
    vient_de_se_resoudre = (
        not created and ancien != IncidentPublic.Statut.RESOLVED
        and instance.statut == IncidentPublic.Statut.RESOLVED)

    # NTOBS26 — bus core.events (consommé par apps.publicapi pour le webhook
    # sortant), pour TOUT incident (système OU société) — distinct de la
    # notification email ci-dessous, réservée aux incidents SYSTÈME.
    if created:
        _emettre_incident_opened(instance)
    elif vient_de_se_resoudre:
        _emettre_incident_resolved(instance)

    if instance.company_id is not None:
        return  # jamais un incident société-spécifique aux abonnés publics

    if created:
        _envoyer_notification_abonnes(instance, 'ouvert')
    elif vient_de_se_resoudre:
        _envoyer_notification_abonnes(instance, 'resolu')


def _emettre_incident_opened(incident):
    """NTOBS26 — best-effort : un abonné cassé sur le bus ne doit jamais
    empêcher la création de l'incident lui-même."""
    try:
        from core.events import incident_opened
        incident_opened.send(
            sender=IncidentPublic, incident=incident, company=incident.company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'NTOBS26 : émission incident_opened échouée (incident %s)',
            incident.pk)


def _emettre_incident_resolved(incident):
    """NTOBS26 — best-effort, même garde que ``_emettre_incident_opened``."""
    try:
        from core.events import incident_resolved
        incident_resolved.send(
            sender=IncidentPublic, incident=incident, company=incident.company)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.exception(
            'NTOBS26 : émission incident_resolved échouée (incident %s)',
            incident.pk)


def _abonnes_de_la_region(region):
    return StatusSubscriber.objects.filter(confirme=True).filter(
        Q(region_filtre='') | Q(region_filtre=region))


def _envoyer_notification_abonnes(incident, evenement):
    from django.conf import settings
    from django.core.mail import send_mail

    sujet = (
        f'[Statut] {incident.titre}' if evenement == 'ouvert'
        else f'[Statut] Résolu — {incident.titre}')
    corps = (
        f'{incident.titre}\n\nSévérité : {incident.severite}\n'
        f'Statut : {incident.statut}\n'
    )
    for abonne in _abonnes_de_la_region(incident.region):
        try:
            lien_desabonnement = (
                '/api/django/statuspage/public/desabonner/'
                f'{abonne.token_desabonnement}/')
            send_mail(
                sujet,
                f'{corps}\nSe désabonner : {lien_desabonnement}',
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local'),
                [abonne.email],
                fail_silently=True,
            )
        except Exception:  # noqa: BLE001 — un envoi KO n'affecte pas les autres
            logger.exception(
                'statuspage._envoyer_notification_abonnes: échec pour %s',
                abonne.email)
