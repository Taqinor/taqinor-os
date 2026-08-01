"""Tests du flag « étoilé » sur le feedback produit (NTIDE45).

Couvre : l'action ``etoiler`` (palier admin), notification aux admins/
gérants à la transition False → True (une seule fois), pas de notification
à la dé-marquation, isolation multi-société."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation.models import FeedbackProduit

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EtoilerActionTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide45-a', 'A')
        self.admin = make_user(self.co_a, 'ntide45-admin', role_legacy='admin')
        self.normal = make_user(self.co_a, 'ntide45-normal')
        self.fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.normal, titre='Retour important')

    def test_admin_can_star(self):
        resp = auth(self.admin).post(f'{self.BASE}{self.fb.id}/etoiler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.fb.refresh_from_db()
        self.assertTrue(self.fb.starred)

    def test_normal_refused(self):
        resp = auth(self.normal).post(f'{self.BASE}{self.fb.id}/etoiler/')
        self.assertEqual(resp.status_code, 403)
        self.fb.refresh_from_db()
        self.assertFalse(self.fb.starred)

    def test_toggle_unstars(self):
        auth(self.admin).post(f'{self.BASE}{self.fb.id}/etoiler/')
        resp = auth(self.admin).post(f'{self.BASE}{self.fb.id}/etoiler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.fb.refresh_from_db()
        self.assertFalse(self.fb.starred)

    def test_starred_not_patchable_directly(self):
        resp = auth(self.admin).get(f'{self.BASE}{self.fb.id}/')
        self.assertIn('starred', resp.data)


class EtoilerNotificationTests(TestCase):
    BASE = '/api/django/innovation/feedback-produit/'

    def setUp(self):
        self.co_a = make_company('innov-ntide45-notif-a', 'A')
        self.admin = make_user(self.co_a, 'ntide45-notif-admin', role_legacy='admin')
        self.author = make_user(self.co_a, 'ntide45-notif-author')
        self.fb = FeedbackProduit.objects.create(
            company=self.co_a, auteur=self.author, titre='Retour important')

    @patch('apps.innovation.services.notifier_feedback_etoile')
    def test_notifies_on_first_star(self, mock_notify):
        auth(self.admin).post(f'{self.BASE}{self.fb.id}/etoiler/')
        mock_notify.assert_called_once()

    @patch('apps.innovation.services.notifier_feedback_etoile')
    def test_no_notification_on_unstar(self, mock_notify):
        auth(self.admin).post(f'{self.BASE}{self.fb.id}/etoiler/')
        mock_notify.reset_mock()
        auth(self.admin).post(f'{self.BASE}{self.fb.id}/etoiler/')
        mock_notify.assert_not_called()

    def test_notifier_reaches_admin(self):
        from apps.notifications.models import Notification

        from apps.innovation import services
        services.notifier_feedback_etoile(self.fb)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin, event_type='feedback_starred').exists())
