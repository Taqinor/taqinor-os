"""Tests FG368 — gestion des jobs planifiés (Celery Beat).

Couvre :
  * normalisation d'un ``beat_schedule`` patché (forme + description cadence) ;
  * garde planning vide / absent → ``[]`` ;
  * dégradation propre quand django-celery-beat n'est pas installé ;
  * liste blanche d'exécution (``known_task_names`` / refus tâche inconnue) ;
  * ``run_job`` appelle bien ``send_task`` (mocké) et renvoie l'id ;
  * ``run_job`` ne plante pas si le broker est injoignable → ``RuntimeError`` ;
  * endpoint : gate admin (403 non-admin), liste (admin), run mocké,
    run d'une tâche inconnue (400), run broker-down (503).

Le découplage est respecté : la cible des tests n'importe AUCUNE app domaine —
seulement ``core.jobs`` / ``core.views`` (infra Celery uniquement).
"""
from unittest import mock

from celery.schedules import crontab
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import jobs as jobs_infra
from core.views import ScheduledJobViewSet

User = get_user_model()

_FAKE_SCHEDULE = {
    'notifications-daily-digest': {
        'task': 'notifications.daily_digest',
        'schedule': crontab(hour=7, minute=30),
    },
    'crm-appointment-reminders': {
        'task': 'crm.appointment_reminders',
        'schedule': crontab(minute='*/15'),
    },
}


def _patch_schedule(schedule):
    """Patche ``current_app.conf.beat_schedule`` ET neutralise la lecture DB
    (django-celery-beat absent → ``_from_periodic_tasks`` renvoie []).
    """
    return mock.patch.object(
        jobs_infra.current_app.conf, 'beat_schedule', schedule, create=True,
    )


class ListJobsUnitTests(TestCase):
    def test_normalized_shape_from_patched_schedule(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            jobs = jobs_infra.list_jobs()
        self.assertEqual(len(jobs), 2)
        # Trié par nom : crm-… avant notifications-…
        first = jobs[0]
        self.assertEqual(
            set(first.keys()),
            {'name', 'task', 'schedule', 'enabled', 'source', 'last_run'},
        )
        self.assertEqual(first['name'], 'crm-appointment-reminders')
        self.assertEqual(first['task'], 'crm.appointment_reminders')
        self.assertTrue(first['enabled'])
        self.assertEqual(first['source'], 'beat_schedule')
        self.assertIsNone(first['last_run'])
        # La cadence est rendue de façon lisible (non vide).
        self.assertTrue(first['schedule'])

    def test_empty_schedule_returns_empty(self):
        with _patch_schedule({}):
            self.assertEqual(jobs_infra.list_jobs(), [])

    def test_missing_schedule_returns_empty(self):
        with _patch_schedule(None):
            self.assertEqual(jobs_infra.list_jobs(), [])

    def test_malformed_entries_are_skipped(self):
        bad = {'x': 'not-a-dict', 'y': {'task': 'a.b', 'schedule': None}}
        with _patch_schedule(bad):
            jobs = jobs_infra.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['task'], 'a.b')

    def test_degrades_without_django_celery_beat(self):
        # django-celery-beat n'est pas une dépendance : la lecture DB doit
        # rendre [] sans erreur, donc list_jobs == beat_schedule seul.
        with _patch_schedule(_FAKE_SCHEDULE):
            self.assertEqual(jobs_infra._from_periodic_tasks(), [])
            self.assertEqual(len(jobs_infra.list_jobs()), 2)


class RunJobUnitTests(TestCase):
    def test_known_task_names_whitelist(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            names = jobs_infra.known_task_names()
        self.assertIn('notifications.daily_digest', names)
        self.assertIn('crm.appointment_reminders', names)

    def test_run_unknown_task_raises_value_error(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            with self.assertRaises(ValueError):
                jobs_infra.run_job('not.a.scheduled.task')

    def test_run_calls_send_task_and_returns_id(self):
        fake_result = mock.Mock(id='abc-123')
        with _patch_schedule(_FAKE_SCHEDULE):
            with mock.patch.object(
                jobs_infra.current_app, 'send_task', return_value=fake_result,
            ) as send:
                task_id = jobs_infra.run_job('notifications.daily_digest')
        send.assert_called_once_with('notifications.daily_digest')
        self.assertEqual(task_id, 'abc-123')

    def test_run_broker_down_raises_runtime_error_not_crash(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            with mock.patch.object(
                jobs_infra.current_app, 'send_task',
                side_effect=OSError('broker unreachable'),
            ):
                with self.assertRaises(RuntimeError):
                    jobs_infra.run_job('notifications.daily_digest')


class ScheduledJobEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='Taqinor Test')
        cls.admin = User.objects.create_user(
            username='fg368_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.normal = User.objects.create_user(
            username='fg368_user', password='x', role_legacy='normal',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def _list(self, user):
        view = ScheduledJobViewSet.as_view({'get': 'list'})
        req = self.factory.get('/jobs/')
        force_authenticate(req, user=user)
        return view(req)

    def _run(self, user, body):
        view = ScheduledJobViewSet.as_view({'post': 'run'})
        req = self.factory.post('/jobs/run/', body, format='json')
        force_authenticate(req, user=user)
        return view(req)

    def test_list_forbidden_for_non_admin(self):
        resp = self._list(self.normal)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_ok_for_admin(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            resp = self._list(self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(
            set(resp.data[0].keys()),
            {'name', 'task', 'schedule', 'enabled', 'source', 'last_run'},
        )

    def test_run_forbidden_for_non_admin(self):
        resp = self._run(self.normal, {'task': 'notifications.daily_digest'})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_run_requires_task_field(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            resp = self._run(self.admin, {})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_run_unknown_task_is_400(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            resp = self._run(self.admin, {'task': 'nope.nope'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_run_calls_send_task_mocked(self):
        fake_result = mock.Mock(id='zzz-999')
        with _patch_schedule(_FAKE_SCHEDULE):
            with mock.patch.object(
                jobs_infra.current_app, 'send_task', return_value=fake_result,
            ) as send:
                resp = self._run(
                    self.admin, {'task': 'notifications.daily_digest'})
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(resp.data['task_id'], 'zzz-999')
        send.assert_called_once_with('notifications.daily_digest')

    def test_run_broker_down_is_503_not_500(self):
        with _patch_schedule(_FAKE_SCHEDULE):
            with mock.patch.object(
                jobs_infra.current_app, 'send_task',
                side_effect=OSError('broker unreachable'),
            ):
                resp = self._run(
                    self.admin, {'task': 'notifications.daily_digest'})
        self.assertEqual(
            resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
