"""NTSEC22 — Tests de la procédure break-glass auditée.

Garanties : motif obligatoire ; l'octroi élève l'accès pour la durée fixée ;
il contourne enforce-SSO ; expire/révoque automatiquement (restaure le rôle) ;
chaque usage est tracé ; scopé société ; MFA exigée côté Directeur.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditLog
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase
from testkit.factories import UserFactory

from apps.identity.breakglass import grant_break_glass, revoke_expired
from apps.identity.models import BreakGlassGrant, IdentityProvider
from apps.identity.selectors import (
    is_break_glass_active, local_password_login_blocked,
)


class BreakGlassServiceTests(TestCase):
    def setUp(self):
        from testkit.factories import CompanyFactory
        self.company = CompanyFactory()
        self.target = UserFactory(company=self.company, username='ops')

    def test_grant_elevates_and_audits(self):
        before = AuditLog.objects.filter(
            action=AuditLog.Action.SECURITY_ALERT).count()
        grant = grant_break_glass(
            target=self.target, motif='incident prod', duree_minutes=30,
            accorde_par=None)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role_legacy, CustomUser.ROLE_ADMIN)
        self.assertTrue(grant.est_actif)
        self.assertTrue(is_break_glass_active(self.target))
        self.assertGreater(
            AuditLog.objects.filter(
                action=AuditLog.Action.SECURITY_ALERT).count(), before)

    def test_bypasses_enforce_sso(self):
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='Okta',
            actif=True, enforce_sso=True)
        # Sans break-glass, le login local est bloqué.
        self.assertTrue(local_password_login_blocked(self.target))
        grant_break_glass(
            target=self.target, motif='urgence', duree_minutes=30,
            accorde_par=None)
        self.target.refresh_from_db()
        # Avec break-glass actif, le login local redevient permis.
        self.assertFalse(local_password_login_blocked(self.target))

    def test_expired_grant_auto_revoked_restores_role(self):
        self.target.role_legacy = CustomUser.ROLE_NORMAL
        self.target.save()
        grant = grant_break_glass(
            target=self.target, motif='x', duree_minutes=30, accorde_par=None)
        BreakGlassGrant.objects.filter(pk=grant.pk).update(
            active_jusqu_a=timezone.now() - timedelta(minutes=1))
        n = revoke_expired()
        self.assertEqual(n, 1)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role_legacy, CustomUser.ROLE_NORMAL)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revoque_le)
        self.assertFalse(is_break_glass_active(self.target))


class BreakGlassEndpointTests(TenantAPITestCase):
    URL = '/api/django/identity/break-glass/'

    def _admin_with_mfa(self):
        admin = UserFactory(
            company=self.company, username='director',
            role_legacy=CustomUser.ROLE_ADMIN)
        admin.totp_enabled = True
        admin.save()
        return admin

    def test_motif_required(self):
        admin = self._admin_with_mfa()
        target = UserFactory(company=self.company, username='t')
        r = self.client_as(user=admin).post(
            self.URL, {'user_id': target.id, 'motif': ''}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_mfa_required(self):
        # Directeur SANS 2FA → 403.
        admin = UserFactory(
            company=self.company, username='nomfa',
            role_legacy=CustomUser.ROLE_ADMIN)
        target = UserFactory(company=self.company, username='t2')
        r = self.client_as(user=admin).post(
            self.URL, {'user_id': target.id, 'motif': 'urgence'},
            format='json')
        self.assertEqual(r.status_code, 403)

    def test_grant_success(self):
        admin = self._admin_with_mfa()
        target = UserFactory(company=self.company, username='t3')
        r = self.client_as(user=admin).post(
            self.URL, {'user_id': target.id, 'motif': 'urgence',
                       'duree_minutes': 30}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        target.refresh_from_db()
        self.assertEqual(target.role_legacy, CustomUser.ROLE_ADMIN)

    def test_non_admin_forbidden(self):
        r = self.client_as().get(self.URL)
        self.assertEqual(r.status_code, 403)

    def test_cannot_grant_cross_tenant(self):
        admin = self._admin_with_mfa()
        foreign = UserFactory(company=self.other_company, username='foreign')
        r = self.client_as(user=admin).post(
            self.URL, {'user_id': foreign.id, 'motif': 'urgence'},
            format='json')
        self.assertEqual(r.status_code, 400)
