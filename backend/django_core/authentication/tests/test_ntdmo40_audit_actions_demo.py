"""NTDMO40 — toutes les actions démo/onboarding passent par `audit.AuditLog`
(réutilise le journal plateforme existant, jamais un nouveau journal) :
reset-demo (NTDMO7), la bascule mode présentation (NTDMO10). La purge
automatique (NTDMO30, `authentication.purger_societes_demo_expirees`) écrit
déjà dans `AuditLog` — couverte par
`test_ntdmo30_purge_demo_expiree.py::test_writes_an_audit_log_before_deletion_that_survives_it`,
non dupliquée ici."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from authentication.models import Company, CustomUser

User = CustomUser


class ModePresentationAuditTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Démo Audit', slug='co-audit-40', est_demo=True)
        self.admin = User.objects.create_user(
            'admin-40', password='x', company=self.company, is_staff=True)

    def _client(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        return c

    def test_toggle_writes_one_audit_log_entry(self):
        before = AuditLog.objects.filter(
            action='demo_mode_toggle').count()
        r = self._client().patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': True})
        self.assertEqual(r.status_code, 200)
        entries = AuditLog.objects.filter(
            action='demo_mode_toggle')
        self.assertEqual(entries.count(), before + 1)
        entry = entries.latest('id')
        self.assertEqual(entry.company_id, self.company.id)
        self.assertEqual(entry.user_id, self.admin.id)
        self.assertIn('activé', entry.detail)

    def test_no_real_change_writes_no_entry(self):
        before = AuditLog.objects.filter(
            action='demo_mode_toggle').count()
        self._client().patch(
            f'/api/django/companies/{self.company.id}/',
            {'mode_presentation_actif': False})
        self.assertEqual(
            AuditLog.objects.filter(
                action='demo_mode_toggle').count(),
            before)


class ResetDemoAuditTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Démo Reset Audit', slug='demo-reset-audit-40', est_demo=True)
        self.admin = User.objects.create_user(
            'admin-reset-40', password='x', company=self.company,
            is_staff=True)

    def _client(self):
        c = APIClient()
        c.force_authenticate(self.admin)
        return c

    def test_reset_demo_writes_an_audit_log_entry_that_survives_the_purge(self):
        before = AuditLog.objects.filter(action='demo_company_reset').count()
        r = self._client().post(
            f'/api/django/companies/{self.company.id}/reset-demo/')
        self.assertEqual(r.status_code, 200)
        entries = AuditLog.objects.filter(action='demo_company_reset')
        self.assertEqual(entries.count(), before + 1)
        entry = entries.latest('id')
        # `AuditLog.company` est SET_NULL (contrairement au chatter
        # `records.Activity`, CASCADE — NTDMO39) : la ligne d'audit posée
        # AVANT la purge survit, FK à None, texte (`detail`) intact.
        self.assertIsNone(entry.company_id)
        self.assertIn('demo-reset-audit-40', entry.detail)
        self.assertIn('admin-reset-40', entry.detail)
