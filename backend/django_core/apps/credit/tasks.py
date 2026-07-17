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
