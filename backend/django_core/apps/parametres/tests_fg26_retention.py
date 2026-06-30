"""FG26 — purge de rétention du journal d'audit (RGPD)."""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role, ADMIN_PERMISSIONS
from apps.parametres.models import CompanyProfile, SettingsAuditLog
from apps.parametres.retention import purge_company_audit
from apps.audit.models import AuditLog

User = get_user_model()


def _company(slug='fg26r-co', nom='FG26R Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class FG26RetentionTest(TestCase):
    def setUp(self):
        self.company = _company()
        self.profile = CompanyProfile.objects.create(
            company=self.company, audit_retention_days=30)

    def _make_old_and_new(self):
        old = timezone.now() - timezone.timedelta(days=60)
        recent = timezone.now() - timezone.timedelta(days=5)
        a_old = AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.LOGIN,
            actor_username='x')
        AuditLog.objects.filter(pk=a_old.pk).update(timestamp=old)
        a_new = AuditLog.objects.create(
            company=self.company, action=AuditLog.Action.LOGIN,
            actor_username='y')
        AuditLog.objects.filter(pk=a_new.pk).update(timestamp=recent)
        s_old = SettingsAuditLog.objects.create(
            company=self.company, section='profil', field='nom')
        SettingsAuditLog.objects.filter(pk=s_old.pk).update(timestamp=old)

    def test_purge_removes_only_beyond_window(self):
        self._make_old_and_new()
        audit_deleted, settings_deleted = purge_company_audit(self.company)
        self.assertEqual(audit_deleted, 1)
        self.assertEqual(settings_deleted, 1)
        self.assertEqual(AuditLog.objects.filter(
            company=self.company).count(), 1)

    def test_unlimited_retention_is_noop(self):
        self.profile.audit_retention_days = 0
        self.profile.save()
        self._make_old_and_new()
        self.assertEqual(purge_company_audit(self.company), (0, 0))

    def test_purge_endpoint_admin_only(self):
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        admin = User.objects.create_user(
            username='fg26r_admin', password='pw', role_legacy='admin',
            role=admin_role, company=self.company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        r = api.post('/api/django/parametres/audit/purge/')
        self.assertEqual(r.status_code, 200, r.content)

        viewer = User.objects.create_user(
            username='fg26r_viewer', password='pw', role_legacy='utilisateur',
            company=self.company)
        api2 = APIClient()
        api2.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(viewer)}')
        r2 = api2.post('/api/django/parametres/audit/purge/')
        self.assertEqual(r2.status_code, 403)
