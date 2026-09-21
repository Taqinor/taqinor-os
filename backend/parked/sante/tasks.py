"""NTSAN31 — Beat Celery quotidien de l'app ``sante`` : alerte J-7 avant
``PriseEnCharge.date_expiration`` pour le secrétariat, évite les actes
réalisés hors couverture.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``), comme
``apps.rh.tasks``/``apps.contrats.scheduled``. Multi-tenant : boucle par
société active (``authentication.Company``), jamais une lecture de company
depuis un corps de requête ; une exception sur l'une n'empêche jamais les
suivantes (best-effort, journalisé).

Idempotence (« pas de doublon si la tâche tourne plusieurs fois ») : miroir
exact du pattern ``apps.rh.tasks.alertes_expiration`` — avant d'émettre, on
vérifie qu'AUCUNE ``Notification`` du même ``event_type`` portant le même
``link`` stable (id de la ``PriseEnCharge``) n'a déjà été créée AUJOURD'HUI
pour ce destinataire.
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

# Réutilisé (même famille sémantique « quelque chose expire »), comme
# apps.rh.tasks/apps.ventes.scheduled — pas de nouveau type d'événement.
_EVENT_PEC_EXPIRATION = 'warranty_expiring'


def _recipients_secretariat(company):
    """Destinataires de l'alerte (secrétariat) : palier admin/responsable
    actifs de la société, à défaut tous les utilisateurs actifs — même
    logique que ``apps.rh.tasks._recipients`` (le rôle dédié
    ``secretaire_medicale`` de NTSAN17 n'est pas encore posé)."""
    try:
        from authentication.models import CustomUser
        base = list(
            CustomUser.objects.filter(company=company, is_active=True))
    except Exception:  # pragma: no cover - défensif
        return []
    managers = []
    for user in base:
        try:
            if getattr(user, 'is_admin_role', False) or getattr(
                    user, 'role_tier', None) in ('admin', 'responsable'):
                managers.append(user)
        except Exception:  # pragma: no cover - défensif
            continue
    return managers or base


def _deja_notifie_aujourdhui(link, recipient_ids):
    """Sous-ensemble de ``recipient_ids`` déjà notifié AUJOURD'HUI pour ce
    ``link`` (même événement)."""
    from apps.notifications.models import Notification

    today = timezone.localdate()
    try:
        return set(
            Notification.objects.filter(
                event_type=_EVENT_PEC_EXPIRATION, link=link,
                recipient_id__in=recipient_ids, created_at__date=today,
            ).values_list('recipient_id', flat=True))
    except Exception:  # pragma: no cover - défensif
        return set()


@shared_task(name='sante.alertes_prise_en_charge_expirant')
def alertes_prise_en_charge_expirant():
    """NTSAN31 — notifie le secrétariat pour chaque ``PriseEnCharge``
    ``accordee`` dont ``date_expiration`` tombe dans EXACTEMENT 7 jours, par
    société active. Une notification déjà émise aujourd'hui pour la même
    ``PriseEnCharge`` n'est jamais réémise (deux exécutions le même jour ne
    doublent jamais l'alerte)."""
    from datetime import timedelta

    from authentication.selectors import active_companies

    from apps.notifications.services import notify
    from .models import PriseEnCharge

    today = timezone.localdate()
    cible = today + timedelta(days=7)
    total_pecs = 0
    total_notifs = 0

    for company in active_companies():
        pecs = PriseEnCharge.objects.filter(
            company=company, date_expiration=cible,
            statut=PriseEnCharge.Statut.ACCORDEE,
        ).select_related('patient', 'convention')
        if not pecs.exists():
            continue
        total_pecs += pecs.count()

        recipients = _recipients_secretariat(company)
        if not recipients:
            continue
        recipient_ids = [u.pk for u in recipients]

        for pec in pecs:
            link = f'/sante/prises-en-charge?id={pec.pk}'
            deja = _deja_notifie_aujourdhui(link, recipient_ids)
            manquants = [u for u in recipients if u.pk not in deja]
            if not manquants:
                continue
            titre = 'Prise en charge expire dans 7 jours'
            corps = (
                f'La prise en charge de {pec.patient} '
                f'({pec.convention}) expire le '
                f'{pec.date_expiration:%d/%m/%Y}.')
            for user in manquants:
                try:
                    notify(
                        user, _EVENT_PEC_EXPIRATION, titre, body=corps,
                        link=link, company=company)
                    total_notifs += 1
                except Exception:  # pragma: no cover - défensif
                    logger.warning(
                        'sante.alertes_prise_en_charge_expirant: '
                        'notification échouée vers %s', user, exc_info=True)

    logger.info(
        'sante.alertes_prise_en_charge_expirant: %s prise(s) en charge '
        'traitée(s), %s notification(s) émise(s)', total_pecs, total_notifs)
    return {'prises_en_charge': total_pecs, 'notifications': total_notifs}
