"""apps.credit.tasks — jobs Celery beat du module crédit (best-effort, jamais
bloquants). Enregistrés dans ``erp_agentique/celery.py::beat_schedule``.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _casablanca_today():
    from django.utils import timezone
    try:
        from zoneinfo import ZoneInfo
        return timezone.now().astimezone(ZoneInfo('Africa/Casablanca')).date()
    except Exception:  # pragma: no cover
        return timezone.localdate()


def alerter_exposition_globale_pour_societe(company, *, today=None):
    """NTCRD21 — si l'encours consolidé de ``company`` dépasse
    ``ReglageCredit.seuil_alerte_exposition_globale`` (>0), notifie les
    admins/Directeurs UNE seule fois par jour (dédup
    ``derniere_alerte_exposition_le``). Best-effort. Renvoie ``True`` si une
    alerte a été émise."""
    from decimal import Decimal

    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    from .models import ReglageCredit
    from .selectors import rapport_exposition

    today = today or _casablanca_today()
    reglage = ReglageCredit.objects.filter(company=company).first()
    if reglage is None:
        return False
    seuil = reglage.seuil_alerte_exposition_globale or Decimal('0')
    if seuil <= 0:
        return False
    # Dédup : déjà alerté aujourd'hui → no-op.
    if reglage.derniere_alerte_exposition_le == today:
        return False

    total = sum(
        (ligne['encours'] for ligne in rapport_exposition(company)),
        Decimal('0'))
    if total <= seuil:
        return False

    from authentication.models import CustomUser
    destinataires = list(CustomUser.admins_actifs_qs(company))
    title = 'Alerte : exposition crédit société élevée'
    body = (
        f'Encours consolidé {total} MAD > seuil {seuil} MAD. '
        'Revue de portefeuille recommandée.')
    notify_many(
        destinataires, EventType.DIGEST, title, body=body, company=company)

    reglage.derniere_alerte_exposition_le = today
    reglage.save(update_fields=['derniere_alerte_exposition_le'])
    return True


def recalculer_encours_pour_societe(company):
    """NTCRD32 — rafraîchit le cache d'encours (``EncoursCache``) de tous les
    clients d'une société. Idempotent (upsert). Renvoie le nombre de clients
    rafraîchis."""
    from apps.crm.selectors import client_base_qs

    from .models import EncoursCache
    from .selectors import encours_client

    n = 0
    for client in client_base_qs(company):
        EncoursCache.objects.update_or_create(
            client=client,
            defaults={'company': company, 'encours': encours_client(client)})
        n += 1
    return n


@shared_task(name='credit.recalculer_encours_quotidien')
def recalculer_encours_quotidien():
    """NTCRD32 — job quotidien : rafraîchit le cache d'encours de toutes les
    sociétés (best-effort). Renvoie le total de clients rafraîchis."""
    from authentication.models import Company

    total = 0
    for company in Company.objects.all():
        try:
            total += recalculer_encours_pour_societe(company)
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning(
                'credit.recalculer_encours_quotidien: société %s échouée : %s',
                getattr(company, 'id', '?'), exc)
    return total


@shared_task(name='credit.expirer_derogations')
def expirer_derogations(now=None):
    """NTCRD33 — passe au statut ``expiree`` toute ``DerogationCredit``
    APPROUVEE dont ``valide_jusqu_au`` est dépassée, et notifie le demandeur
    d'origine (best-effort). Renvoie le nombre de dérogations expirées."""
    from django.utils import timezone

    from apps.notifications.models import EventType
    from apps.notifications.services import notify

    from .models import DerogationCredit

    now = now or timezone.now()
    echues = DerogationCredit.objects.filter(
        statut=DerogationCredit.Statut.APPROUVEE,
        valide_jusqu_au__isnull=False,
        valide_jusqu_au__lt=now,
    )
    n = 0
    for d in echues:
        d.statut = DerogationCredit.Statut.EXPIREE
        d.save(update_fields=['statut'])
        n += 1
        if d.demandeur_id:
            try:
                notify(
                    d.demandeur, EventType.DIGEST,
                    'Dérogation crédit expirée',
                    body=(
                        f'La dérogation pour le client {d.client_id} '
                        f'({d.montant_demande} MAD) a expiré.'),
                    company=d.company)
            except Exception as exc:  # pragma: no cover - best-effort
                logger.warning('credit.expirer_derogations notify: %s', exc)
    return n


@shared_task(name='credit.alerter_polices_expirantes')
def alerter_polices_expirantes(today=None):
    """NTCRD34 — job hebdomadaire : notifie le Directeur quand une
    ``PoliceAssuranceCredit`` active approche sa ``date_fin`` (J-30), une seule
    fois (dédup ``derniere_alerte_le``). Renvoie le nombre d'alertes émises."""
    from datetime import timedelta

    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    from .models import PoliceAssuranceCredit

    today = today or _casablanca_today()
    horizon = today + timedelta(days=30)
    from authentication.models import CustomUser

    emises = 0
    polices = PoliceAssuranceCredit.objects.filter(
        actif=True, date_fin__isnull=False,
        date_fin__gte=today, date_fin__lte=horizon,
    )
    for police in polices:
        # Dédup simple : si déjà alertée aujourd'hui (marqueur en base), skip.
        if police.derniere_alerte_le == today:
            continue
        destinataires = list(CustomUser.admins_actifs_qs(police.company))
        try:
            notify_many(
                destinataires, EventType.DIGEST,
                "Police d'assurance-crédit proche de l'échéance",
                body=(
                    f'{police.assureur} ({police.numero_police}) expire le '
                    f'{police.date_fin}. Renouvellement à prévoir.'),
                company=police.company)
            police.derniere_alerte_le = today
            police.save(update_fields=['derniere_alerte_le'])
            emises += 1
        except Exception as exc:  # pragma: no cover - best-effort
            logger.warning('credit.alerter_polices_expirantes: %s', exc)
    return emises


@shared_task(name='credit.alerter_exposition_globale')
def alerter_exposition_globale():
    """NTCRD21 — balaye toutes les sociétés et émet l'alerte d'exposition
    consolidée (best-effort, une par jour et par société). Renvoie le nombre
    d'alertes émises."""
    from authentication.models import Company

    today = _casablanca_today()
    emises = 0
    for company in Company.objects.all():
        try:
            if alerter_exposition_globale_pour_societe(company, today=today):
                emises += 1
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning(
                'credit.alerter_exposition_globale: société %s échouée : %s',
                getattr(company, 'id', '?'), exc)
    return emises
