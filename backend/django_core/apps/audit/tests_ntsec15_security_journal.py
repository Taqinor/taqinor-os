"""NTSEC15 — Journal de sécurité dédié & exportable.

Garanties : le sélecteur ne renvoie que les actions de sécurité de LA société
(jamais d'une autre), respecte la fenêtre temporelle, et l'export CSV réservé
au Directeur reprend ces mêmes lignes scopées.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from authentication.models import CustomUser
from testkit.base import TenantAPITestCase

from apps.audit.models import AuditLog
from apps.audit.selectors import security_events


class SecurityEventsSelectorTests(TestCase):
    def setUp(self):
        from testkit.factories import CompanyFactory
        self.company = CompanyFactory()
        self.other = CompanyFactory()

    def _log(self, action, company, detail='', when=None):
        entry = AuditLog.objects.create(
            company=company, action=action, detail=detail)
        if when is not None:
            AuditLog.objects.filter(pk=entry.pk).update(timestamp=when)
        return entry

    def test_only_security_actions(self):
        self._log(AuditLog.Action.LOGIN, self.company)
        self._log(AuditLog.Action.SECURITY_ALERT, self.company)
        self._log(AuditLog.Action.CREATE, self.company)  # non-sécurité
        qs = security_events(self.company)
        actions = set(qs.values_list('action', flat=True))
        self.assertEqual(actions, {'login', 'security_alert'})

    def test_company_scoped(self):
        self._log(AuditLog.Action.LOGIN, self.company)
        self._log(AuditLog.Action.LOGIN, self.other)
        self.assertEqual(security_events(self.company).count(), 1)

    def test_time_window(self):
        now = timezone.now()
        self._log(AuditLog.Action.LOGIN, self.company,
                  when=now - timedelta(days=10))
        self._log(AuditLog.Action.LOGIN, self.company, when=now)
        recent = security_events(self.company, since=now - timedelta(days=1))
        self.assertEqual(recent.count(), 1)

    def test_none_company_empty(self):
        self.assertEqual(security_events(None).count(), 0)


class SecurityExportTests(TenantAPITestCase):
    URL = '/api/django/audit/security/export/'

    def test_directeur_can_export_csv(self):
        AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.SECURITY_ALERT,
            detail='alerte test')
        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r['Content-Type'], 'text/csv')
        body = r.content.decode('utf-8')
        self.assertIn('timestamp', body)
        self.assertIn('security_alert', body)

    def test_non_directeur_forbidden(self):
        r = self.client_as().get(self.URL)
        self.assertIn(r.status_code, (403, 401))

    def test_export_is_company_scoped(self):
        AuditLog.objects.create(
            company=self.other_company,
            action=AuditLog.Action.SECURITY_ALERT, detail='foreign')
        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(self.URL)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('foreign', r.content.decode('utf-8'))
