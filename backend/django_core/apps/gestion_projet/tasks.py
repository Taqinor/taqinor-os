"""AUD231 — jobs planifiés de la gestion de projet (XPRJ13 / XPRJ22 / XPRJ7).

Défaut d'origine : les trois commandes de gestion ci-dessous annonçaient dans
leur docstring « Pensé pour être exécuté à la demande ou par un planificateur
(cron / Celery beat) » alors que le grep sur ``erp_agentique/`` rendait ZÉRO —
aucune entrée de ``beat_schedule``, aucune tâche Celery. Les tâches récurrentes
n'étaient donc jamais générées, et ni les retards de projet ni les temps
manquants n'étaient jamais notifiés, tant que personne ne lançait la commande à
la main.

Autodécouvert par ``erp_agentique.celery`` (``autodiscover_tasks()``). Chaque
enveloppe boucle PAR société (jamais une company lue d'une requête) et appelle
le SERVICE — jamais la commande, ni une logique dupliquée ; une exception sur
une société n'empêche jamais les suivantes (best-effort, journalisé).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _companies():
    from authentication.models import Company
    return list(Company.objects.all())


@shared_task(name='gestion_projet.generer_taches_recurrentes')
def generer_taches_recurrentes_task():
    """XPRJ13 (AUD231) — génère la prochaine ``Tache`` de chaque récurrence
    active à échéance, pour toutes les sociétés. Idempotente : deux passages le
    même jour ne créent jamais deux occurrences pour la même échéance. Renvoie
    le nombre total de tâches créées."""
    from .services import generer_taches_recurrentes
    total = 0
    for company in _companies():
        try:
            total += len(generer_taches_recurrentes(company))
        except Exception:  # noqa: BLE001 — société suivante
            logger.warning(
                'gestion_projet.generer_taches_recurrentes: échec société %s',
                company.id, exc_info=True)
    return total


@shared_task(name='gestion_projet.alertes_retards_projets')
def alertes_retards_projets_task():
    """XPRJ22 (AUD231) — notifie le responsable de chaque projet ACTIF en
    retard/à risque, pour toutes les sociétés. Idempotente : jamais deux
    alertes pour le même (projet, élément) le même jour. Renvoie le nombre
    total d'alertes envoyées."""
    from .services import alertes_retards_projets
    envoyees = 0
    for company in _companies():
        try:
            envoyees += alertes_retards_projets(company).get(
                'nb_alertes_envoyees', 0)
        except Exception:  # noqa: BLE001 — société suivante
            logger.warning(
                'gestion_projet.alertes_retards_projets: échec société %s',
                company.id, exc_info=True)
    return envoyees


@shared_task(name='gestion_projet.rappels_timesheets')
def rappels_timesheets_task():
    """XPRJ7 (AUD231) — notifie les ressources en retard de saisie de temps sur
    les 7 derniers jours (même fenêtre par défaut que la commande), pour toutes
    les sociétés. Idempotente : une ressource n'est jamais notifiée deux fois
    pour la même fenêtre le même jour. Renvoie le nombre total de
    notifications envoyées."""
    from datetime import date, timedelta
    from .services import rappeler_temps_manquants
    aujourd_hui = date.today()
    debut = aujourd_hui - timedelta(days=7)
    notifies = 0
    for company in _companies():
        try:
            notifies += rappeler_temps_manquants(
                company, debut, aujourd_hui).get('nb_notifies', 0)
        except Exception:  # noqa: BLE001 — société suivante
            logger.warning(
                'gestion_projet.rappels_timesheets: échec société %s',
                company.id, exc_info=True)
    return notifies
