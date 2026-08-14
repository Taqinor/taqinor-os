"""Tâches Celery de l'app authentication — autodécouvertes par
`erp_agentique.celery` (`app.autodiscover_tasks()`), aucun enregistrement manuel.

WIR50 — enveloppe planifiable de la désactivation des comptes dormants
(NTSEC25). Sans entrée beat, la commande ne tournait que lancée à la main : un
compte inactif au-delà du seuil société restait actif indéfiniment.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='authentication.desactiver_comptes_dormants')
def desactiver_comptes_dormants_task():
    """NTSEC25 — désactive les comptes dormants (balayage PAR SOCIÉTÉ).

    Enveloppe fine : délègue à la commande homonyme, qui porte toute
    l'orchestration (seuil ``CompanyProfile.dormant_days`` par société,
    notification préalable au Directeur, révocation des sessions). Idempotente ;
    no-op tant qu'aucune société n'a armé de seuil (> 0)."""
    from django.core.management import call_command

    call_command('desactiver_comptes_dormants')
    logger.info('authentication.desactiver_comptes_dormants: balayage terminé.')
    return {'ok': True}


@shared_task(name='authentication.seed_demo_company_wizard')
def seed_demo_company_task(slug, profil='mixte', densite='complet'):
    """NTDMO25 — enveloppe Celery du wizard « Créer ma société de
    démonstration ». Délègue tout à la commande homonyme (mêmes options
    additives ``--profil``/``--densite``) ; la progression est tracée via le
    cache (``views_demo_wizard.set_progress``)."""
    from .views_demo_wizard import _run_wizard

    _run_wizard(slug, profil, densite)
    logger.info('authentication.seed_demo_company_wizard: %s (%s/%s) prêt.',
                slug, profil, densite)
    return {'slug': slug, 'statut': 'termine'}


@shared_task(name='authentication.purger_societes_demo_expirees')
def purger_societes_demo_expirees_task():
    """NTDMO30 — purge HEBDOMADAIRE des sociétés de démonstration TAQINOR
    expirées (staging/marketing uniquement, jamais une société réelle).

    Garde-fou : no-op TOTAL tant que ``settings.DEMO_AUTO_PURGE_ENABLED``
    n'est pas explicitement activé (désactivé par défaut, même convention que
    ``GED_PURGE_AUTO_APPLY``/``BACKUP_PURGE_AUTO_APPLY``/
    ``RETENTION_AUTO_APPLY``) — aucune société n'est jamais supprimée en
    production tant que le founder ne pose pas ce drapeau. Cible : ``est_demo=
    True`` (filtre strict — jamais une société réelle) ET
    ``CompanyProfile.essai_expire_le`` (NTDMO20) dépassé de plus de 90 jours.
    Un ``AuditLog`` (``apps.audit``) est écrit AVANT chaque suppression (survit
    à la cascade — ``AuditLog.company`` est ``SET_NULL``). La suppression
    elle-même réutilise le même mécanisme ORM (jamais de SQL brut) que
    ``reset_demo_company`` (gère les FK ``PROTECT`` via ``_delete_cascading``).
    """
    from django.conf import settings

    if not getattr(settings, 'DEMO_AUTO_PURGE_ENABLED', False):
        logger.info(
            'authentication.purger_societes_demo_expirees: désactivé '
            '(DEMO_AUTO_PURGE_ENABLED=0) — aucune société purgée.')
        return {'purged': 0, 'enabled': False}

    from datetime import timedelta

    from django.utils import timezone

    from apps.audit import recorder
    from authentication.management.commands.reset_demo_company import (
        _delete_cascading,
    )

    from .models import Company, CustomUser

    cutoff = timezone.now().date() - timedelta(days=90)
    # ``est_demo=True`` en premier : ce filtre à lui seul garantit qu'aucune
    # société réelle n'entre jamais dans ce queryset, quel que soit l'état de
    # son profil.
    expirees = list(Company.objects.filter(
        est_demo=True, profile__essai_expire_le__lt=cutoff))

    purged = []
    for company in expirees:
        slug = company.slug
        recorder.record(
            'demo_company_purge', instance=company, company=company,
            user=None, actor_username='celery-beat',
            detail=(f'Société démo "{slug}" purgée automatiquement '
                    '(essai expiré depuis plus de 90 jours).'))
        # CustomUser.company est SET_NULL → supprimer explicitement les
        # comptes de la société démo (sinon ils seraient orphelinés), même
        # séquence que reset_demo_company.
        CustomUser.objects.filter(company=company).delete()
        _delete_cascading(company)
        purged.append(slug)

    logger.info(
        'authentication.purger_societes_demo_expirees: %d société(s) '
        'purgée(s) : %s', len(purged), purged)
    return {'purged': len(purged), 'slugs': purged, 'enabled': True}
