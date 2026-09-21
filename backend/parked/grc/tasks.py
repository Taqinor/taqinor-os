"""NTGRC34 — tâche Celery Beat ``grc.rappels_grc``.

``erp_agentique/celery.py`` planifie l'entrée ``grc-rappels-echeances`` qui
référence la tâche nommée ``grc.rappels_grc``. Ce module (auto-découvert par
``app.autodiscover_tasks()``) ne fait que RELAYER vers la commande de gestion
``rappels_grc`` : une seule logique, un seul comportement, testable sans
broker — et surtout pas une seconde implémentation qui dériverait de la
première.

Le piège que ce module évite est mesuré dans ce dépôt : une entrée de
``beat_schedule`` pointant vers une tâche qu'AUCUN module n'enregistre échoue
en silence à chaque tick (« Received unregistered task »).
"""


def run_rappels_grc():
    """Cœur de la tâche Beat, isolé de la décoration Celery (donc testable)."""
    from django.core.management import call_command

    call_command('rappels_grc')


try:
    from celery import shared_task

    @shared_task(name='grc.rappels_grc')
    def rappels_grc_task():
        """Balayage quotidien des échéances GRC — voir ``run_rappels_grc``."""
        run_rappels_grc()
except ImportError:  # pragma: no cover - celery absent en environnement léger
    pass
