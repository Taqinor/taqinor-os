"""NTSEC13 — Tests détection nouvel appareil / navigateur inconnu.

Garanties : une première connexion depuis un UA jamais vu déclenche une
``SECURITY_ALERT`` ; les connexions suivantes du même appareil non ; scope
société respecté.
"""
from django.test import TestCase

from apps.audit.models import AuditLog
from authentication.device import compute_fingerprint, note_login_device
from authentication.models import UserSession
from testkit.factories import CompanyFactory, UserFactory


class NewDeviceTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(company=self.company, username='dev1')

    def _session(self, ua, jti):
        return UserSession.objects.create(
            company=self.company, user=self.user, jti=jti,
            user_agent=ua, revoked=False)

    def _alerts(self):
        return AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT,
            company=self.company).count()

    def test_first_device_raises_alert(self):
        s = self._session('Mozilla/5.0 Chrome/120', 'j1')
        before = self._alerts()
        raised = note_login_device(self.user, s)
        self.assertTrue(raised)
        self.assertEqual(self._alerts(), before + 1)
        s.refresh_from_db()
        self.assertTrue(s.device_fingerprint)

    def test_same_device_no_alert(self):
        s1 = self._session('Mozilla/5.0 Chrome/120', 'j1')
        note_login_device(self.user, s1)
        before = self._alerts()
        s2 = self._session('Mozilla/5.0 Chrome/120', 'j2')
        raised = note_login_device(self.user, s2)
        self.assertFalse(raised)
        self.assertEqual(self._alerts(), before)

    def test_different_device_alerts_again(self):
        s1 = self._session('Mozilla/5.0 Chrome/120', 'j1')
        note_login_device(self.user, s1)
        before = self._alerts()
        s2 = self._session('Mozilla/5.0 Firefox/121', 'j2')
        raised = note_login_device(self.user, s2)
        self.assertTrue(raised)
        self.assertEqual(self._alerts(), before + 1)

    def test_empty_ua_no_alert(self):
        s = self._session('', 'j1')
        self.assertFalse(note_login_device(self.user, s))

    def test_fingerprint_stable(self):
        a = compute_fingerprint('UA-x', 'Windows')
        b = compute_fingerprint('UA-x', 'Windows')
        self.assertEqual(a, b)
        self.assertNotEqual(a, compute_fingerprint('UA-y', 'Windows'))
