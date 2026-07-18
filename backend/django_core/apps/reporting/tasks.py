"""WIR22 — tâche Celery Beat `reporting.controle_integrite`.

`erp_agentique/celery.py` planifie déjà l'entrée Beat hebdomadaire
``reporting-controle-integrite-hebdo`` qui référence la tâche nommée
``reporting.controle_integrite`` — mais AUCUNE tâche Celery portant ce nom
n'était enregistrée nulle part dans le repo : Beat échouait silencieusement
chaque semaine (``Received unregistered task of type 'reporting.controle_integrite'``),
et `total_anomalies` n'était donc jamais consulté par personne.

Ce module (auto-découvert par ``app.autodiscover_tasks()``, voir
``erp_agentique/celery.py``) relaie vers la commande de gestion
``controle_integrite`` (déjà éprouvée, testée dans ``tests_integrity.py``)
qui parcourt TOUTES les sociétés et notifie (in-app, best-effort via
``notifications.notify_many`` -> ``notifications.notify``) les admins/
responsables dès qu'au moins une anomalie est détectée. Lecture seule : ne
corrige RIEN automatiquement."""


def run_controle_integrite_beat():
    """Cœur de la tâche Beat, isolé de la décoration Celery pour rester
    testable sans dépendre d'un broker (mêmes principes que
    ``kpi_alertes.evaluate_all_kpi_alertes``)."""
    from django.core.management import call_command
    call_command('controle_integrite')


try:
    from celery import shared_task

    @shared_task(name='reporting.controle_integrite')
    def controle_integrite_task():
        """Tâche Beat hebdomadaire (lundi 03:00, Africa/Casablanca) : voir
        ``run_controle_integrite_beat`` pour la logique réelle."""
        run_controle_integrite_beat()
except ImportError:  # pragma: no cover - celery absent en environnement de test
    pass
