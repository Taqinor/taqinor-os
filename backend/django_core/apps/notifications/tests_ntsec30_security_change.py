"""NTSEC30 — Notification obligatoire de changement de sécurité.

Garanties : un changement de facteur de sécurité génère une notification à
l'utilisateur qu'il ne peut PAS couper via ses préférences ; best-effort
(jamais bloquant) ; scope société.
"""
from django.test import TestCase, override_settings

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.types_evenements import EventType
from apps.notifications.services import notify_security_change
from testkit.factories import CompanyFactory, UserFactory

_LOCMEM = {'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@override_settings(CACHES=_LOCMEM)
class SecurityChangeNotifyTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, username='u')

    def test_creates_in_app_notification(self):
        notify_security_change(self.user, 'Mot de passe modifié', 'corps')
        n = Notification.objects.filter(
            recipient=self.user,
            event_type=EventType.SECURITY_CHANGE).first()
        self.assertIsNotNone(n)
        self.assertEqual(n.company_id, self.company.id)
        self.assertEqual(n.title, 'Mot de passe modifié')

    def test_bypasses_in_app_preference_opt_out(self):
        # L'utilisateur coupe le canal in-app pour cet événement…
        NotificationPreference.objects.create(
            user=self.user, event_type=EventType.SECURITY_CHANGE,
            in_app=False, email=False)
        notify_security_change(self.user, 'MFA désactivée', 'corps')
        # …la notification de SÉCURITÉ est émise malgré tout (non désactivable).
        self.assertTrue(Notification.objects.filter(
            recipient=self.user,
            event_type=EventType.SECURITY_CHANGE).exists())

    def test_none_user_noop(self):
        self.assertIsNone(notify_security_change(None, 't', 'b'))

    def test_transaction_annulee_aucun_email(self):
        """ASOC31 (C-ASOC-140) — changement annulé par la transaction : 0 ligne,
        0 e-mail ; transaction validée : 1 ligne, 1 e-mail APRÈS le commit."""
        from unittest import mock

        from django.db import transaction
        with mock.patch(
                'apps.notifications.services._dispatch_email') as envoi:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError):
                    with transaction.atomic():
                        notify_security_change(
                            self.user, 'Mot de passe modifié')
                        raise RuntimeError('annulé')
            envoi.assert_not_called()
            lignes = Notification.objects.filter(
                recipient=self.user, event_type=EventType.SECURITY_CHANGE)
            self.assertEqual(lignes.count(), 0)
            with self.captureOnCommitCallbacks(execute=False) as rappels:
                notify_security_change(self.user, 'Mot de passe modifié')
            envoi.assert_not_called()  # pas avant le commit
            for rappel in rappels:
                rappel()
            envoi.assert_called_once()
            self.assertEqual(lignes.count(), 1)

    def test_scoped_to_user_company(self):
        notify_security_change(self.user, 't', 'b')
        n = Notification.objects.get(recipient=self.user)
        self.assertEqual(n.company_id, self.company.id)
