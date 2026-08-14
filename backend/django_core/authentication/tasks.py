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
