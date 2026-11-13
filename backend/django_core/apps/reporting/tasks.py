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
from importlib import import_module


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


def run_recalcul_nocturne_onboarding():
    """NTDMO31/41/42 — UN job nocturne : résumé démo de chaque société démo
    (``demo_resume``) + KPI internes d'onboarding (``onboarding_kpi``), tous
    deux servis ensuite depuis le cache. Une brique en échec n'arrête pas
    l'autre."""
    import logging
    from . import demo_resume, onboarding_kpi

    log = logging.getLogger(__name__)
    out = {'societes_demo': 0, 'kpi_interne': False}
    try:
        out['societes_demo'] = demo_resume.precalculer_societes_demo()
    except Exception:  # pragma: no cover - défensif
        log.warning('recalcul nocturne : résumés démo en échec', exc_info=True)
    try:
        onboarding_kpi.precalculer()
        out['kpi_interne'] = True
    except Exception:  # pragma: no cover - défensif
        log.warning('recalcul nocturne : KPI onboarding en échec', exc_info=True)
    return out


try:
    @shared_task(name='reporting.recalcul_nocturne_onboarding')
    def recalcul_nocturne_onboarding_task():
        """Tâche Beat quotidienne (nuit) — voir ``run_recalcul_nocturne_onboarding``."""
        return run_recalcul_nocturne_onboarding()
except NameError:  # pragma: no cover - celery absent
    pass


# NTEXT12 — l'envoi planifié des abonnements vit dans son propre module ; on
# l'importe ICI pour que ``app.autodiscover_tasks()`` (qui ne regarde que
# ``tasks.py``) enregistre bien ``reporting.envoyer_rapports_planifies``.
try:  # pragma: no cover - dépend de la présence de celery
    import_module(f'{__package__}.rapport_abonnements')
    # ACEL38 — idem pour ``reporting.evaluate_kpi_alertes`` (jusqu'ici
    # enregistrée seulement par l'import des URLs, absent avec CELERY_SKIP_CHECKS).
    import_module(f'{__package__}.kpi_alertes')
except ImportError:  # pragma: no cover
    pass
