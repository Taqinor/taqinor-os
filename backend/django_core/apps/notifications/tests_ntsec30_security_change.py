"""NTSEC30 — Notification obligatoire de changement de sécurité.

Garanties : un changement de facteur de sécurité génère une notification à
l'utilisateur qu'il ne peut PAS couper via ses préférences ; best-effort
(jamais bloquant) ; scope société.
"""
from django.test import TestCase, override_settings

from apps.notifications.models import (
    EventType, Notification, NotificationPreference,
)
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

    def test_scoped_to_user_company(self):
        notify_security_change(self.user, 't', 'b')
        n = Notification.objects.get(recipient=self.user)
        self.assertEqual(n.company_id, self.company.id)
