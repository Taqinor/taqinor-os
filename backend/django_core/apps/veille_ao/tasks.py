"""VAO22 — la tâche planifiée de la veille, livrée DÉSARMÉE.

**Pourquoi 06:00 (Africa/Casablanca)** : les remises de plis sont à 10 h-11 h.
L'information du matin est donc actionnable LE JOUR MÊME ; la même collecte à
midi arriverait après la bataille.

**Pourquoi désarmée** — règle #5 volet (b) : la première exécution réelle exige
l'accord explicite et daté du fondateur (tâche VAO4). Tant que
``VEILLE_AO_COLLECTE_ACTIVE`` vaut ``0`` — le DÉFAUT — la tâche sort
immédiatement, sans toucher la base et sans le moindre appel réseau. Aucun
agent ne peut l'armer de sa propre initiative : c'est un drapeau
d'environnement, posé en production par un humain.

L'entrée ``beat_schedule`` est OBLIGATOIRE (``apps/ventes/tests/
test_qx11_beat_reachability.py`` fait rougir la CI sur toute tâche planifiée
absente du beat) : elle est présente et inerte. Une entrée présente + un
drapeau à 0 est HONNÊTE — l'écran « Tâches planifiées » montre la tâche, et
``sante`` dit qu'elle est désarmée. Une tâche absente du beat serait le mode de
défaillance dominant du dépôt : bâtie, testée, jamais exécutée.

Les tâches prennent des CLÉS PRIMAIRES, jamais des instances de modèle (garde
``scripts/check_celery_tasks.py``).
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

__all__ = ['collecte_active', 'collecte_quotidienne']


def collecte_active():
    """L'interrupteur d'armement (règle #5, VAO4). ``False`` par défaut.

    Lu à CHAQUE exécution, jamais mis en cache au chargement du module : le
    fondateur doit pouvoir désarmer sans redéployer.
    """
    return bool(getattr(settings, 'VEILLE_AO_COLLECTE_ACTIVE', False))


#: Le message rendu quand la tâche sort sans rien faire. Il NOMME la tâche
#: d'armement : un « désactivé » nu envoie l'utilisateur chercher pourquoi.
MOTIF_DESARME = (
    "Collecte désarmée (VEILLE_AO_COLLECTE_ACTIVE=0) : aucun appel réseau. "
    "L'armement est une décision fondateur datée (VAO4).")


@shared_task(name='veille_ao.collecte_quotidienne')
def collecte_quotidienne(job_id=None, company_id=None, user_id=None):
    """Collecte du matin — inerte tant que la collecte n'est pas ARMÉE.

    Deux déclencheurs, UNE mécanique (VAO23) : le beat de 06:00 l'appelle sans
    argument (toutes les sociétés), le bouton « Rafraîchir maintenant » la
    soumet par ``core.jobs.submit`` avec ``job_id``/``company_id``. Il n'existe
    pas de second chemin de collecte « pour le bouton » — c'est ainsi qu'on
    obtient deux comportements divergents.

    Renvoie toujours un dictionnaire ; ne lève jamais (une panne devient un
    ``BackgroundJob`` en échec + un journal d'exécution en échec, VAO24).
    """
    from core.models import BackgroundJob

    job = (BackgroundJob.objects.filter(pk=job_id).first()
           if job_id is not None else None)

    if not collecte_active():
        logger.info('veille_ao.collecte_quotidienne : %s', MOTIF_DESARME)
        if job is not None:
            job.marquer_termine()
        return {'arme': False, 'motif': MOTIF_DESARME, 'executions': []}

    try:
        if job is not None:
            job.marquer_progression(5)
        resultats = _collecter_les_societes(company_id)
        if job is not None:
            job.marquer_termine()
        return {'arme': True, 'motif': '', 'executions': resultats}
    except Exception as erreur:  # noqa: BLE001 — toute panne = échec PROPRE
        logger.exception('veille_ao.collecte_quotidienne : échec')
        if job is not None:
            job.marquer_echec(str(erreur))
        return {'arme': True, 'motif': str(erreur), 'executions': []}


def _collecter_les_societes(company_id=None):
    """Lance la collecte pour UNE société, ou pour toutes (beat de nuit).

    Chaque société est indépendante : une société en panne n'empêche pas les
    autres de collecter.
    """
    from authentication.models import Company

    from .services import collecter_toutes_les_sources

    societes = Company.objects.all()
    if company_id is not None:
        societes = societes.filter(pk=company_id)

    resultats = []
    for company in societes:
        try:
            resultats.extend(collecter_toutes_les_sources(company))
        except Exception as erreur:  # noqa: BLE001 — société isolée
            logger.exception(
                'veille_ao: collecte de la société %s échouée', company.pk)
            resultats.append({'source_id': None, 'source': '',
                              'verdict': 'echec', 'message': str(erreur)})
    return resultats
