"""ENG15 — Tests des assets créatifs (CRUD + upload + garde policy).

Invariant DUR (testé) : un asset dont ``policy_stamp.passed`` n'est pas vrai ne
peut PAS être référencé par une ``EngineAction`` de création d'ad — ni en
proposition manuelle, ni en auto-apply (ENG8).
"""
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import CreativeAsset, EngineAction, GuardrailConfig

User = get_user_model()
BASE = '/api/django/adsengine/creatifs/'


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


class PolicyStampEnforcementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PS Co', slug='ps-co')

    def _asset(self, passed):
        stamp = {'passed': True, 'rules_checked': ['r1'],
                 'checked_at': '2026-07-16', 'checked_by': 1} if passed else {}
        return CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp=stamp)

    def test_unstamped_asset_blocks_create_ad_proposal(self):
        asset = self._asset(passed=False)
        self.assertFalse(asset.is_policy_passed)
        with self.assertRaises(services.CreativePolicyNotPassed):
            services.propose_action(
                self.company, kind=EngineAction.Kind.CREATE_AD,
                reason_fr="Créer une ad avec ce créatif.",
                payload={'name': 'Ad', 'adset_id': 'as1',
                         'creative_asset_id': asset.id})

    def test_stamped_asset_allows_create_ad_proposal(self):
        asset = self._asset(passed=True)
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.CREATE_AD,
            reason_fr="Créer une ad avec ce créatif validé.",
            payload={'name': 'Ad', 'adset_id': 'as1',
                     'creative_asset_id': asset.id})
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_missing_creative_id_is_noop(self):
        # Sans creative_asset_id référencé, aucune contrainte policy.
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.CREATE_AD,
            reason_fr="Créer une ad sans créatif référencé.",
            payload={'name': 'Ad', 'adset_id': 'as1'})
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_unstamped_asset_blocks_auto_rotate(self):
        GuardrailConfig.objects.create(
            company=self.company, auto_rotate_creative=True)
        asset = self._asset(passed=False)
        with self.assertRaises(services.CreativePolicyNotPassed):
            services.execute_auto_action(
                self.company, kind=EngineAction.Kind.ROTATE_CREATIVE,
                reason_fr="Roter vers ce créatif.",
                payload={'name': 'Ad', 'adset_id': 'as1',
                         'creative_asset_id': asset.id},
                client=Mock())


class CreativeAssetApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CA Co', slug='ca-co')
        self.manager = make_user(
            self.company, 'manager', ['adsengine_view', 'adsengine_manage'])

    def test_create_asset_forces_company(self):
        other = Company.objects.create(nom='Other', slug='other-ca')
        resp = auth(self.manager).post(BASE, {
            'asset_type': 'static', 'cost_cents': 500,
            'company': other.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        asset = CreativeAsset.objects.get(id=resp.data['id'])
        self.assertEqual(asset.company_id, self.company.id)
        # policy_stamp vide par défaut → non validé.
        self.assertFalse(asset.is_policy_passed)

    def test_upload_stores_and_creates_pending_asset(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile('x.png', b'\x89PNG', content_type='image/png')
        with patch('apps.records.storage.store_attachment',
                   return_value=({'file_key': 'adsengine/1/abc.png',
                                  'filename': 'x.png', 'size': 4,
                                  'mime': 'image/png'}, None)) as mock_store:
            resp = auth(self.manager).post(
                f'{BASE}upload/', {'file': fake, 'asset_type': 'static'},
                format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        mock_store.assert_called_once()
        self.assertEqual(resp.data['file_key'], 'adsengine/1/abc.png')
        self.assertFalse(resp.data['is_policy_passed'])

    def test_list_is_company_scoped(self):
        other = Company.objects.create(nom='O', slug='o-ca')
        CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC)
        CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.REEL)
        resp = auth(self.manager).get(BASE)
        results = resp.data['results'] if 'results' in resp.data else resp.data
        self.assertEqual(len(results), 1)

    def test_response_includes_provenance_for_manual_upload(self):
        # PUB84 — un asset jamais issu d'un lot de génération ancrée (upload
        # manuel) reste un batch_id None + son policy_stamp, jamais une 500.
        asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={'passed': True})
        resp = auth(self.manager).get(f'{BASE}{asset.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('provenance', resp.data)
        self.assertIsNone(resp.data['provenance']['batch_id'])
        self.assertEqual(
            resp.data['provenance']['policy_stamp'], {'passed': True})
