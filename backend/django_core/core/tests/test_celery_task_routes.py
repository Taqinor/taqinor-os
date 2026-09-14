"""Tests YOPSB9 — isolation des queues Celery par classe de travail.

Couvre le routage d'au moins une tâche `interactive` (rendu PDF déclenché
par une action utilisateur) et une tâche `scheduled` (job beat), et que la
queue par défaut reste `default` (comportement mono-worker inchangé)."""
from django.conf import settings
from django.test import SimpleTestCase


class CeleryTaskRoutesTests(SimpleTestCase):
    def test_devis_pdf_routes_to_interactive(self):
        route = settings.CELERY_TASK_ROUTES['ventes.generate_devis_pdf']
        self.assertEqual(route['queue'], 'interactive')

    def test_facture_pdf_routes_to_interactive(self):
        route = settings.CELERY_TASK_ROUTES['ventes.generate_facture_pdf']
        self.assertEqual(route['queue'], 'interactive')

    def test_chat_transcription_routes_to_interactive(self):
        route = settings.CELERY_TASK_ROUTES[
            'chat.transcribe_voice_attachment']
        self.assertEqual(route['queue'], 'interactive')

    def test_expire_stale_devis_routes_to_scheduled(self):
        route = settings.CELERY_TASK_ROUTES['ventes.expire_stale_devis']
        self.assertEqual(route['queue'], 'scheduled')

    def test_all_beat_schedule_tasks_are_routed_to_scheduled_or_interactive(self):
        """Chaque tâche présente dans le beat_schedule (erp_agentique/celery.py)
        doit être routée — jamais laissée sur `default` par oubli."""
        from erp_agentique.celery import app

        beat_task_names = {
            entry['task'] for entry in app.conf.beat_schedule.values()
        }
        missing = [
            name for name in beat_task_names
            if name not in settings.CELERY_TASK_ROUTES
        ]
        self.assertEqual(missing, [],
                         f'Tâches planifiées sans route explicite : {missing}')
        for name in beat_task_names:
            self.assertEqual(
                settings.CELERY_TASK_ROUTES[name]['queue'], 'scheduled',
                f'{name} devrait router vers scheduled')

    def test_default_queue_unchanged(self):
        self.assertEqual(settings.CELERY_TASK_DEFAULT_QUEUE, 'default')

    def test_all_beat_schedule_tasks_are_registered(self):
        """Incident prod du 14/09/2026 : 42 tâches planifiées au beat n'étaient
        enregistrées par AUCUN worker (déclarées hors `tasks.py`, jamais
        importées au boot) — beat les envoyait dans le vide, le worker les
        rejetait en boucle (« unregistered task ») et les fonctionnalités
        correspondantes (relances, rappels RDV, digests, reprises
        d'automatisation) ne tournaient silencieusement jamais. Chaque tâche
        du beat_schedule DOIT exister dans le registre Celery après la même
        autodécouverte qu'au démarrage d'un worker."""
        from erp_agentique.celery import app

        # Déclenche l'autodécouverte EXACTEMENT comme au boot d'un worker :
        # `autodiscover_tasks()` (lazy) s'abonne au signal `import_modules`,
        # que le worker émet via `loader.import_default_modules()` —
        # `app.finalize()` seul ne suffit PAS (vérifié : il n'importe pas
        # les modules `tasks.py`).
        app.loader.import_default_modules()
        beat_task_names = {
            entry['task'] for entry in app.conf.beat_schedule.values()
        }
        missing = sorted(beat_task_names - set(app.tasks))
        self.assertEqual(
            missing, [],
            'Tâches planifiées au beat mais absentes du registre Celery '
            f'(module jamais importé par le worker ?) : {missing}')
