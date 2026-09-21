"""apps.migration.tasks — jobs Celery beat du groupe NTMIG.

Enregistrés dans ``erp_agentique/celery.py::beat_schedule`` ET dans
``CELERY_TASK_ROUTES`` (settings/base.py, queue ``scheduled``) — une tâche
planifiée laissée sur la queue par défaut serait consommée par le mauvais
worker.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='migration.purger_fichiers_migration')
def purger_fichiers_migration():
    """NTMIG35 — purge des fichiers source (PII) des projets clôturés.

    Quotidien, best-effort, jamais bloquant : les rapports de réconciliation
    (agrégats non-PII) sont conservés, seuls les fichiers téléversés sont
    supprimés du stockage objet.
    """
    from . import services

    resultat = services.purger_fichiers_expires()
    if resultat['fichiers']:
        logger.info(
            'NTMIG35 — %s fichier(s) source purgé(s) sur %s projet(s).',
            resultat['fichiers'], resultat['projets'])
    return resultat


# ── NTMIG30 — alerte d'expiration de certification partenaire ──────────────
#
# Réutilise le PATTERN d'échéances RH (FG175/YHIRE8, ``apps.rh.tasks``) : même
# type d'événement (``warranty_expiring`` — « pas de nouveau type
# d'événement »), même déduplication quotidienne par ``link`` stable, mais
# jamais son CODE (la fiche concernée est ``crm.Partenaire``, pas une
# habilitation RH — famille distincte, cf. ``crm.selectors.
# certifications_expirantes``).

_EVENT_CERTIFICATION = 'warranty_expiring'


def _destinataires_certification(company):
    """Responsables/admin actifs de la société, à défaut tous les actifs.

    Même logique que ``rh.tasks._recipients`` — dupliquée localement (chaque
    app porte son propre petit helper de destinataires, pattern déjà suivi
    par ``rh``/``sav``/``sante``/``transport``), jamais un import croisé.
    """
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


def _deja_notifie_aujourdhui(event_type, link, recipient_ids):
    """Sous-ensemble de ``recipient_ids`` déjà notifié aujourd'hui pour ce
    ``link`` — permet de ne notifier que les destinataires manquants."""
    from django.utils import timezone

    from apps.notifications.models import Notification

    today = timezone.localdate()
    try:
        return set(
            Notification.objects.filter(
                event_type=event_type, link=link,
                recipient_id__in=recipient_ids,
                created_at__date=today,
            ).values_list('recipient_id', flat=True))
    except Exception:  # pragma: no cover - défensif
        return set()


@shared_task(name='migration.alerter_certifications_expirantes')
def alerter_certifications_expirantes(within_days=60):
    """NTMIG30 — notifie UNE fois par jour et par échéance les responsables/
    admin des partenaires dont la CERTIFICATION expire sous ``within_days``
    jours (défaut 60), par société active.

    Réutilise ``crm.selectors.certifications_expirantes`` (pur/testable) —
    cette tâche n'ajoute que la diffusion + la déduplication quotidienne.
    Isolation par société : une exception sur l'une n'empêche jamais les
    suivantes (best-effort, journalisé).
    """
    from authentication.selectors import active_companies

    from apps.crm import selectors as crm_selectors
    from apps.notifications.services import notify

    total_echeances = 0
    total_notifs = 0

    for company in active_companies():
        try:
            partenaires = list(
                crm_selectors.certifications_expirantes(
                    company, within_days=within_days))
        except Exception:  # pragma: no cover - défensif, isolation société
            logger.warning(
                'migration.alerter_certifications_expirantes: échec '
                'sélecteur société %s', company.pk, exc_info=True)
            continue
        if not partenaires:
            continue
        total_echeances += len(partenaires)

        destinataires = _destinataires_certification(company)
        if not destinataires:
            continue
        recipient_ids = [u.pk for u in destinataires]

        for partenaire in partenaires:
            echeance = partenaire.date_expiration_certification
            link = (
                f'/admin/partenaires-certifies?partenaire={partenaire.pk}'
                f'&echeance={echeance.isoformat()}')
            deja = _deja_notifie_aujourdhui(
                _EVENT_CERTIFICATION, link, recipient_ids)
            manquants = [u for u in destinataires if u.pk not in deja]
            if not manquants:
                continue
            titre = (
                f'Certification {partenaire.get_niveau_certification_display()} '
                f'— {partenaire.nom} (expire le {echeance.isoformat()})')[:255]
            corps = f'Échéance de certification : {echeance.isoformat()}.'
            for user in manquants:
                try:
                    notify(
                        user, _EVENT_CERTIFICATION, titre, body=corps,
                        link=link, company=company)
                    total_notifs += 1
                except Exception:  # pragma: no cover - défensif
                    logger.warning(
                        'migration.alerter_certifications_expirantes: '
                        'notification échouée vers %s', user, exc_info=True)

    logger.info(
        'migration.alerter_certifications_expirantes: %s échéance(s) '
        'traitée(s), %s notification(s) émise(s)',
        total_echeances, total_notifs)
    return {'echeances': total_echeances, 'notifications': total_notifs}
