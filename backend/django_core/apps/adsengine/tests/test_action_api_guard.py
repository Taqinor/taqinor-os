"""ENGFIX2 — La garde policy créative couvre AUSSI le POST direct du ViewSet.

``EngineActionViewSet`` est un ModelViewSet (POST activé) sans surcharge de
création : un ``create_ad`` référençant un ``CreativeAsset`` non estampillé
policy passait outre ``assert_creative_ok_for_ad`` (appelé seulement par les
services). On prouve ici que ``perform_create`` réenclenche la garde (400 sur un
asset non validé, 201 sur un asset validé) et que la société est forcée serveur.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import CreativeAsset, EngineAction

User = get_user_model()
BASE = '/api/django/adsengine/actions/'


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


class CreateAdApiPolicyGuardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='API Guard', slug='api-guard')
        self.manager = make_user(
            self.company, 'manager', ['adsengine_view', 'adsengine_manage'])

    def _asset(self, passed):
        stamp = ({'passed': True, 'rules_checked': ['r1'],
                  'checked_at': '2026-07-16', 'checked_by': 1}
                 if passed else {})
        return CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp=stamp)

    def _post_create_ad(self, asset):
        return auth(self.manager).post(BASE, {
            'kind': 'create_ad',
            'reason_fr': "Créer une ad avec ce créatif.",
            'payload': {'name': 'Ad', 'adset_id': 'as1',
                        'creative_asset_id': asset.id},
        }, format='json')

    def test_unstamped_asset_rejected_400(self):
        asset = self._asset(passed=False)
        resp = self._post_create_ad(asset)
        self.assertEqual(resp.status_code, 400, resp.data)
        # Aucune action n'est créée (la garde bloque avant save).
        self.assertFalse(EngineAction.objects.filter(
            company=self.company).exists())

    def test_stamped_asset_accepted_201(self):
        asset = self._asset(passed=True)
        resp = self._post_create_ad(asset)
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(id=resp.data['id'])
        # Société forcée côté serveur, statut initial proposee.
        self.assertEqual(action.company_id, self.company.id)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_asset_from_other_company_rejected_400(self):
        # Un asset (même estampillé) d'une AUTRE société est introuvable dans la
        # portée de l'appelant → la garde refuse (jamais de fuite cross-tenant).
        other = Company.objects.create(nom='Other', slug='other-guard')
        foreign = CreativeAsset.objects.create(
            company=other, asset_type=CreativeAsset.AssetType.STATIC,
            policy_stamp={'passed': True})
        resp = self._post_create_ad(foreign)
        self.assertEqual(resp.status_code, 400, resp.data)
