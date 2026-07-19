"""PUB75 — Registre de consentement image/témoignage (CNDP loi 09-08).

Prouve : CRUD company-scopé (``company`` posée côté serveur), la GARDE
consentement dans la passe policy (asset « client réel » sans consentement →
policy FAIL explicite), le retrait de rotation à la révocation, et les états
expiré / portée insuffisante.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import policy
from apps.adsengine.models import (
    ConsentRecord, CreativeAsset, CreativeBacklogItem,
)

User = get_user_model()

BASE = '/api/django/adsengine/consentements/'


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=username + '-role', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='normal', role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def make_consent(company, **kw):
    defaults = dict(
        company=company, client_nom='Client Test',
        portee_photo=True, portee_temoignage=True,
        date_consentement=datetime.date(2026, 1, 1))
    defaults.update(kw)
    return ConsentRecord.objects.create(**defaults)


class ConsentCrudTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Consent Co', slug='consent-co')
        self.user = make_user(
            self.company, 'consent_mgr',
            ['adsengine_view', 'adsengine_manage'])

    def test_create_forces_company_server_side(self):
        other = Company.objects.create(nom='Consent B', slug='consent-b')
        resp = auth(self.user).post(BASE, {
            'client_nom': 'M. Diffusable',
            'canal': 'whatsapp',
            'portee_photo': True,
            'date_consentement': '2026-02-01',
            'company': other.id,  # tentative d'injection — ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        rec = ConsentRecord.objects.get(id=resp.data['id'])
        self.assertEqual(rec.company_id, self.company.id)
        self.assertIn('photo', resp.data['scopes'])
        self.assertTrue(resp.data['is_active'])

    def test_list_is_company_scoped(self):
        make_consent(self.company)
        other = Company.objects.create(nom='Consent C', slug='consent-c')
        make_consent(other)
        resp = auth(self.user).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_revoked_at_is_read_only(self):
        rec = make_consent(self.company)
        now = timezone.now().isoformat()
        resp = auth(self.user).patch(
            f'{BASE}{rec.id}/', {'revoked_at': now}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        rec.refresh_from_db()
        self.assertIsNone(rec.revoked_at)


class ConsentModelTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CM Co', slug='cm-co')

    def test_is_active_and_covers(self):
        rec = make_consent(self.company, portee_photo=True, portee_geo=False)
        self.assertTrue(rec.is_active())
        self.assertTrue(rec.covers('photo'))
        self.assertFalse(rec.covers('geo'))
        self.assertFalse(rec.covers('inconnu'))

    def test_expired_consent_not_active(self):
        rec = make_consent(
            self.company, expiration=datetime.date(2020, 1, 1))
        self.assertFalse(rec.is_active())

    def test_revoked_consent_not_active(self):
        rec = make_consent(self.company)
        rec.revoked_at = timezone.now()
        self.assertFalse(rec.is_active())


class ConsentPolicyGuardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CG Co', slug='cg-co')

    def _asset(self, **kw):
        defaults = dict(
            company=self.company,
            asset_type=CreativeAsset.AssetType.STATIC,
            depicts_real_client=True)
        defaults.update(kw)
        return CreativeAsset.objects.create(**defaults)

    def _confirm_all(self, asset):
        # Confirme TOUTES les règles interdites (l'humain atteste).
        forbidden, _ = policy._policy_rules(self.company)
        keys = [r['key'] for r in forbidden]
        return policy.record_policy_check(asset, confirmed_keys=keys)

    def test_real_client_without_consent_fails(self):
        asset = self._asset()
        self._confirm_all(asset)
        asset.refresh_from_db()
        self.assertFalse(asset.is_policy_passed)
        self.assertEqual(asset.policy_stamp['consent_block'], 'manquant')

    def test_real_client_with_active_consent_passes(self):
        consent = make_consent(
            self.company, portee_photo=True)
        asset = self._asset(
            consent=consent, consent_scopes_required=['photo'])
        self._confirm_all(asset)
        asset.refresh_from_db()
        self.assertTrue(asset.is_policy_passed)
        self.assertNotIn('consent_block', asset.policy_stamp)

    def test_scope_not_covered_blocks(self):
        consent = make_consent(
            self.company, portee_photo=True, portee_temoignage=False)
        asset = self._asset(
            consent=consent, consent_scopes_required=['temoignage'])
        self._confirm_all(asset)
        asset.refresh_from_db()
        self.assertFalse(asset.is_policy_passed)
        self.assertEqual(asset.policy_stamp['consent_block'], 'portee')

    def test_expired_consent_blocks(self):
        consent = make_consent(
            self.company, portee_photo=True,
            expiration=datetime.date(2020, 1, 1))
        asset = self._asset(consent=consent)
        self._confirm_all(asset)
        asset.refresh_from_db()
        self.assertEqual(asset.policy_stamp['consent_block'], 'expire')

    def test_non_client_asset_unaffected(self):
        asset = self._asset(depicts_real_client=False)
        self._confirm_all(asset)
        asset.refresh_from_db()
        self.assertTrue(asset.is_policy_passed)

    def test_revocation_removes_asset_from_rotation(self):
        consent = make_consent(self.company, portee_photo=True)
        asset = self._asset(
            consent=consent, consent_scopes_required=['photo'])
        self._confirm_all(asset)
        asset.refresh_from_db()
        self.assertTrue(asset.is_policy_passed)
        # File de rotation : l'asset validé est comptabilisé.
        CreativeBacklogItem.objects.create(
            company=self.company, asset=asset)
        ready = CreativeAsset.objects.filter(
            company=self.company, policy_stamp__passed=True)
        self.assertIn(asset, list(ready))
        # Révocation → retrait immédiat de la rotation.
        retires = consent.revoke()
        self.assertEqual(retires, 1)
        asset.refresh_from_db()
        self.assertFalse(asset.is_policy_passed)
        self.assertEqual(asset.policy_stamp['consent_block'], 'revoque')
        ready = CreativeAsset.objects.filter(
            company=self.company, policy_stamp__passed=True)
        self.assertNotIn(asset, list(ready))

    def test_revoke_is_idempotent(self):
        consent = make_consent(self.company, portee_photo=True)
        asset = self._asset(consent=consent)
        self._confirm_all(asset)
        consent.revoke()
        # Deuxième révocation : aucun asset re-écrit (déjà retiré).
        self.assertEqual(consent.revoke(), 0)
