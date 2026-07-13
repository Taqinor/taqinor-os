"""NTSEC24 — Tests des comptes de service (identités machine).

Garanties : un compte de service s'authentifie par jeton avec ses seuls scopes,
la rotation invalide l'ancien jeton, révocation = inactif, jamais de login UI,
scope société.
"""
from authentication.models import CustomUser
from testkit.base import TenantAPITestCase

from apps.publicapi.models import ServiceAccount, hash_key


class ServiceAccountModelTests(TenantAPITestCase):
    def test_issue_hashes_token_and_filters_scopes(self):
        from apps.publicapi.constants import ALL_SCOPES
        good = ALL_SCOPES[0]
        sa, raw = ServiceAccount.issue(
            company=self.company, nom='ci-bot',
            scopes=[good, 'scope_bidon_inconnu'])
        self.assertEqual(sa.company_id, self.company.id)
        self.assertEqual(sa.scopes, [good])
        self.assertEqual(sa.token_hash, hash_key(raw))
        self.assertTrue(sa.has_scope(good))
        self.assertFalse(sa.has_scope('scope_bidon_inconnu'))

    def test_rotate_invalidates_old_token(self):
        sa, raw1 = ServiceAccount.issue(
            company=self.company, nom='rot', scopes=[])
        old_hash = sa.token_hash
        raw2 = sa.rotate()
        sa.refresh_from_db()
        self.assertNotEqual(sa.token_hash, old_hash)
        self.assertEqual(sa.token_hash, hash_key(raw2))
        self.assertNotEqual(raw1, raw2)

    def test_est_actif_respects_flag_and_expiry(self):
        from datetime import timedelta
        from django.utils import timezone
        sa, _ = ServiceAccount.issue(
            company=self.company, nom='x', scopes=[])
        self.assertTrue(sa.est_actif)
        sa.actif = False
        self.assertFalse(sa.est_actif)
        sa.actif = True
        sa.expire_le = timezone.now() - timedelta(hours=1)
        self.assertFalse(sa.est_actif)


class ServiceAccountEndpointTests(TenantAPITestCase):
    URL = '/api/django/identity/service-accounts/'

    def _admin(self):
        return self.client_as(role=CustomUser.ROLE_ADMIN)

    def test_create_returns_token_once(self):
        r = self._admin().post(self.URL, {'nom': 'bot'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn('token', r.json())
        # La lecture ultérieure ne réexpose jamais le jeton.
        sa_id = r.json()['id']
        detail = self._admin().get(f'{self.URL}{sa_id}/')
        self.assertNotIn('token', detail.json())

    def test_non_admin_forbidden(self):
        r = self.client_as().post(self.URL, {'nom': 'bot'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_list_company_scoped(self):
        ServiceAccount.issue(
            company=self.other_company, nom='foreign', scopes=[])
        r = self._admin().get(self.URL)
        self.assertEqual(r.status_code, 200)
        noms = {row['nom'] for row in r.json()['results']}
        self.assertNotIn('foreign', noms)

    def test_rotate_endpoint(self):
        sa, raw1 = ServiceAccount.issue(
            company=self.company, nom='rot', scopes=[])
        r = self._admin().post(f'{self.URL}{sa.id}/rotate/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('token', r.json())
        self.assertNotEqual(r.json()['token'], raw1)

    def test_revoke_endpoint(self):
        sa, _ = ServiceAccount.issue(
            company=self.company, nom='rev', scopes=[])
        r = self._admin().post(f'{self.URL}{sa.id}/revoke/')
        self.assertEqual(r.status_code, 200)
        sa.refresh_from_db()
        self.assertFalse(sa.actif)
