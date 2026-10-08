"""APAR3 — la purge d'audit exposée à l'admin respecte le plancher légal de
365 j (``audit.selectors.effective_retention_days``), se journalise elle-même
et ne purge jamais ses propres lignes de trace (C-APAR-001)."""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.audit.models import AuditLog
from apps.parametres.models import CompanyProfile, SettingsAuditLog
from apps.parametres.retention import (
    PURGE_FIELD, PURGE_SECTION, purge_company_audit,
)
from apps.roles.models import Role
from apps.roles.permissions_registre import ADMIN_PERMISSIONS
from authentication.models import Company

User = get_user_model()


def _age(model, obj, days):
    model.objects.filter(pk=obj.pk).update(
        timestamp=timezone.now() - timezone.timedelta(days=days))


class PurgePlancherTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR3 Co', slug='apar3-co')
        self.profile = CompanyProfile.objects.create(
            company=self.company, audit_retention_days=1)
        role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.admin = User.objects.create_user(
            username='apar3_admin', password='pw', role_legacy='admin',
            role=role, company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _audit(self, days):
        row = AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.LOGIN,
            actor_username='x')
        _age(AuditLog, row, days)
        return row

    def _settings(self, days, section='profil', field='nom'):
        row = SettingsAuditLog.objects.create(
            company=self.company, section=section, field=field)
        _age(SettingsAuditLog, row, days)
        return row

    def test_purge_admin_respecte_365_jours(self):
        for d in (2, 30, 200, 364):
            self._audit(d)
            self._settings(d)
        r = self.api.post('/api/django/parametres/audit/purge/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            r.json(), {'audit_deleted': 0, 'settings_deleted': 0})
        # Persistance : recompter — aucune ligne < 365 j supprimée.
        self.assertEqual(AuditLog.objects.filter(
            company=self.company, actor_username='x').count(), 4)
        self.assertEqual(SettingsAuditLog.objects.filter(
            company=self.company, section='profil').count(), 4)

    def test_ligne_de_400_jours_supprimee(self):
        vieux_a = self._audit(400)
        vieux_s = self._settings(400)
        recent = self._audit(10)
        r = self.api.post('/api/django/parametres/audit/purge/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            r.json(), {'audit_deleted': 1, 'settings_deleted': 1})
        self.assertFalse(AuditLog.objects.filter(pk=vieux_a.pk).exists())
        self.assertFalse(
            SettingsAuditLog.objects.filter(pk=vieux_s.pk).exists())
        self.assertTrue(AuditLog.objects.filter(pk=recent.pk).exists())

    def test_purge_journalisee_au_nom_de_l_admin(self):
        self._audit(400)
        self.api.post('/api/django/parametres/audit/purge/')
        traces = SettingsAuditLog.objects.filter(
            company=self.company, section=PURGE_SECTION, field=PURGE_FIELD)
        self.assertEqual(traces.count(), 1)
        trace = traces.get()
        self.assertEqual(trace.user_id, self.admin.pk)
        self.assertIn('audit_deleted=1', trace.new_value)
        self.assertIn('effective 365', trace.old_value)

    def test_traces_de_purge_jamais_purgees(self):
        trace = self._settings(800, section=PURGE_SECTION, field=PURGE_FIELD)
        purge_company_audit(self.company, user=self.admin)
        self.assertTrue(
            SettingsAuditLog.objects.filter(pk=trace.pk).exists())

    def test_erreur_de_suppression_remonte(self):
        self._audit(400)
        with mock.patch(
                'django.db.models.query.QuerySet.delete',
                side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                purge_company_audit(self.company, user=self.admin)
        # Rien n'a été journalisé comme réussi.
        self.assertFalse(SettingsAuditLog.objects.filter(
            company=self.company, section=PURGE_SECTION).exists())

    def test_retention_illimitee_reste_noop(self):
        self.profile.audit_retention_days = 0
        self.profile.save()
        self._audit(800)
        self.assertEqual(purge_company_audit(self.company), (0, 0))
        self.assertEqual(AuditLog.objects.filter(
            company=self.company, actor_username='x').count(), 1)
