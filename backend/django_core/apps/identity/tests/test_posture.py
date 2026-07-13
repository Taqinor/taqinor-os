"""NTSEC27 — Tests du tableau de bord posture de sécurité.

Garanties : le Directeur voit un score consolidé de SA société avec les items
faibles listés ; lecture seule scopée société ; agrégation best-effort.
"""
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase
from testkit.factories import UserFactory

from apps.identity.models import IdentityProvider
from apps.identity.posture import security_posture


class SecurityPostureTests(TenantAPITestCase):
    URL = '/api/django/identity/posture/'

    def test_selector_returns_expected_keys(self):
        posture = security_posture(self.company)
        for key in ('mfa_pct', 'sso_configured', 'active_sessions',
                    'dormant_accounts', 'sod_open_violations',
                    'overdue_review_campaigns', 'expired_secrets',
                    'ip_allowlist_active', 'score', 'soc2_iso27001_ready',
                    'items_faibles'):
            self.assertIn(key, posture)

    def test_sso_reflected_in_score(self):
        low = security_posture(self.company)
        IdentityProvider.objects.create(
            company=self.company, protocol='saml', nom='Okta', actif=True)
        high = security_posture(self.company)
        self.assertTrue(high['sso_configured'])
        self.assertGreater(high['score'], low['score'])
        self.assertNotIn('SSO non configuré', high['items_faibles'])

    def test_mfa_percentage(self):
        # Un utilisateur MFA sur deux → 50 %.
        u1 = UserFactory(company=self.company, username='mfa1')
        u1.totp_enabled = True
        u1.save()
        UserFactory(company=self.company, username='mfa2')
        posture = security_posture(self.company)
        self.assertGreater(posture['mfa_pct'], 0)

    def test_endpoint_directeur_only(self):
        r = self.client_as(role=CustomUser.ROLE_ADMIN).get(self.URL)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('score', r.json())

    def test_endpoint_non_admin_forbidden(self):
        r = self.client_as().get(self.URL)
        self.assertEqual(r.status_code, 403)

    def test_none_company_empty(self):
        self.assertEqual(security_posture(None), {})
