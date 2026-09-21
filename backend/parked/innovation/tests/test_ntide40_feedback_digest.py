"""Tests du digest feedback produit (NTIDE40).

Couvre : ``tasks.feedback_digest_run`` — gated PAR SOCIÉTÉ via
``InnovationSettings.feedback_digest_actif`` (désactivé par défaut, no-op),
no-op silencieux sans feedback non-lu, notifie les gérants/admins avec le
tag ``EventType.FEEDBACK_DIGEST``, respecte la fréquence hebdo (lundi
seulement)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.innovation import tasks
from apps.innovation.models import FeedbackProduit, InnovationSettings
from apps.notifications.models import EventType, Notification

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


class FeedbackDigestRunTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-ntide40-a', 'A')
        self.admin = make_user(self.co_a, 'ntide40-admin')

    def test_noop_when_digest_not_activated(self):
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.admin, titre='Retour')
        emitted = tasks.feedback_digest_run()
        self.assertEqual(emitted, 0)
        self.assertEqual(
            Notification.objects.filter(
                event_type=EventType.FEEDBACK_DIGEST).count(), 0)

    def test_noop_without_unread_feedback(self):
        InnovationSettings.objects.create(
            company=self.co_a, feedback_digest_actif=True)
        emitted = tasks.feedback_digest_run()
        self.assertEqual(emitted, 0)

    def test_notifies_admin_when_activated_and_unread(self):
        InnovationSettings.objects.create(
            company=self.co_a, feedback_digest_actif=True)
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.admin, titre='Retour non lu')
        emitted = tasks.feedback_digest_run()
        self.assertEqual(emitted, 1)
        notif = Notification.objects.get(event_type=EventType.FEEDBACK_DIGEST)
        self.assertEqual(notif.recipient, self.admin)

    def test_hebdo_frequency_skips_non_monday(self):
        InnovationSettings.objects.create(
            company=self.co_a, feedback_digest_actif=True,
            feedback_digest_frequence=InnovationSettings.Frequence.HEBDO)
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.admin, titre='Retour non lu')
        with mock.patch('django.utils.timezone.now') as mocked_now:
            from django.utils import timezone as real_timezone
            # Un mardi (weekday() == 1), jamais lundi.
            mocked_now.return_value = real_timezone.datetime(
                2026, 7, 14, 9, 0, tzinfo=real_timezone.get_current_timezone())
            emitted = tasks.feedback_digest_run()
        self.assertEqual(emitted, 0)

    def test_hebdo_frequency_runs_on_monday(self):
        InnovationSettings.objects.create(
            company=self.co_a, feedback_digest_actif=True,
            feedback_digest_frequence=InnovationSettings.Frequence.HEBDO)
        FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.admin, titre='Retour non lu')
        with mock.patch('django.utils.timezone.now') as mocked_now:
            from django.utils import timezone as real_timezone
            # Un lundi (weekday() == 0).
            mocked_now.return_value = real_timezone.datetime(
                2026, 7, 13, 9, 0, tzinfo=real_timezone.get_current_timezone())
            emitted = tasks.feedback_digest_run()
        self.assertEqual(emitted, 1)

    def test_task_registered_in_beat_schedule_and_routes(self):
        from django.conf import settings
        from erp_agentique.celery import app
        task_names = {e['task'] for e in app.conf.beat_schedule.values()}
        self.assertIn('innovation.feedback_digest_run', task_names)
        self.assertEqual(
            settings.CELERY_TASK_ROUTES['innovation.feedback_digest_run']['queue'],
            'scheduled')
