"""NTOBS13 — notification proactive au client avant qu'un quota ne soit
atteint (80%/100%). Réutilise entièrement notifications.notify()."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role

from core import usage_limits

User = get_user_model()


def _fake_summary(pct):
    """Résumé usage_summary() minimal avec UNE ressource au pourcentage donné."""
    return {
        'ressources': [
            {'nom': 'Stockage documentaire', 'utilise': pct, 'limite': 100,
             'unite': 'octets'},
        ],
        'genere_le': '2026-01-01T00:00:00',
    }


class NotifierSeuilsUsageTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='Acme', slug='acme-ntobs13')
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur')
        User.objects.create_user(
            'directeur13', password='x', company=self.company,
            role=self.role_directeur)

    def test_crossing_80_percent_notifies_once(self):
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value=_fake_summary(85)), \
                mock.patch('apps.notifications.services.notify') as notify_mock:
            n1 = usage_limits.notifier_seuils_usage()
            n2 = usage_limits.notifier_seuils_usage()
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 0)
        self.assertEqual(notify_mock.call_count, 1)

    def test_crossing_100_percent_after_80_notifies_again(self):
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value=_fake_summary(85)):
            usage_limits.notifier_seuils_usage()
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value=_fake_summary(100)), \
                mock.patch('apps.notifications.services.notify') as notify_mock:
            n = usage_limits.notifier_seuils_usage()
        self.assertEqual(n, 1)
        self.assertTrue(notify_mock.called)

    def test_descending_below_80_resets_and_allows_renotification(self):
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value=_fake_summary(85)):
            usage_limits.notifier_seuils_usage()
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value=_fake_summary(50)):
            usage_limits.notifier_seuils_usage()
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value=_fake_summary(85)), \
                mock.patch('apps.notifications.services.notify') as notify_mock:
            n = usage_limits.notifier_seuils_usage()
        self.assertEqual(n, 1)
        self.assertTrue(notify_mock.called)

    def test_below_80_never_notifies(self):
        with mock.patch(
                'core.usage_limits.usage_summary',
                return_value=_fake_summary(50)), \
                mock.patch('apps.notifications.services.notify') as notify_mock:
            n = usage_limits.notifier_seuils_usage()
        self.assertEqual(n, 0)
        self.assertFalse(notify_mock.called)

    def test_resource_without_limit_is_never_alerted(self):
        summary = {
            'ressources': [
                {'nom': 'Utilisateurs actifs', 'utilise': 500, 'limite': None,
                 'unite': 'comptes'},
            ],
        }
        with mock.patch(
                'core.usage_limits.usage_summary', return_value=summary), \
                mock.patch('apps.notifications.services.notify') as notify_mock:
            n = usage_limits.notifier_seuils_usage()
        self.assertEqual(n, 0)
        self.assertFalse(notify_mock.called)
