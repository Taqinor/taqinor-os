"""ENG16 — Tests de la policy créative (check-list déterministe humaine).

Prouve : le système ENREGISTRE la confirmation humaine (jamais d'évaluation
automatique du contenu) ; ``passed`` n'est vrai que si TOUTES les règles
interdites sont confirmées ; la policy par défaut est seedée ; l'asset validé
débloque la création d'ad (enforcement ENG15).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import policy, services
from apps.adsengine.models import CreativeAsset, CreativePolicy, EngineAction

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


class DefaultPolicyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Pol Co', slug='pol-co')

    def test_ensure_default_policy_is_idempotent(self):
        p1, c1 = policy.ensure_default_policy(self.company)
        p2, c2 = policy.ensure_default_policy(self.company)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(CreativePolicy.objects.count(), 1)

    def test_default_forbidden_rules_present(self):
        policy.ensure_default_policy(self.company)
        checklist = policy.build_checklist(self.company)
        keys = {r['key'] for r in checklist['forbidden']}
        self.assertIn('no_fake_sites', keys)
        self.assertIn('no_unverified_numbers', keys)

    def test_checklist_falls_back_to_defaults_without_policy(self):
        # Aucune policy en base → défauts utilisés (pas de crash).
        checklist = policy.build_checklist(self.company)
        self.assertTrue(checklist['forbidden'])
        self.assertTrue(checklist['allowed'])


class RecordPolicyCheckTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Rec Co', slug='rec-co')
        policy.ensure_default_policy(self.company)
        self.asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)

    def test_all_forbidden_confirmed_passes(self):
        all_keys = [r['key'] for r in policy.DEFAULT_FORBIDDEN]
        policy.record_policy_check(self.asset, confirmed_keys=all_keys)
        self.asset.refresh_from_db()
        self.assertTrue(self.asset.is_policy_passed)
        self.assertEqual(
            self.asset.policy_stamp['rules_checked'], sorted(all_keys))

    def test_partial_confirmation_does_not_pass(self):
        policy.record_policy_check(
            self.asset, confirmed_keys=['no_fake_sites'])
        self.asset.refresh_from_db()
        self.assertFalse(self.asset.is_policy_passed)

    def test_passed_asset_unblocks_create_ad(self):
        all_keys = [r['key'] for r in policy.DEFAULT_FORBIDDEN]
        policy.record_policy_check(self.asset, confirmed_keys=all_keys)
        self.asset.refresh_from_db()
        action = services.propose_action(
            self.company, kind=EngineAction.Kind.CREATE_AD,
            reason_fr="Créer une ad avec un créatif validé.",
            payload={'name': 'Ad', 'adset_id': 'as1',
                     'creative_asset_id': self.asset.id})
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)


class PolicyApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PA Co', slug='pa-co')
        policy.ensure_default_policy(self.company)
        self.manager = make_user(
            self.company, 'manager', ['adsengine_view', 'adsengine_manage'])
        self.asset = CreativeAsset.objects.create(
            company=self.company, asset_type=CreativeAsset.AssetType.STATIC)

    def test_checklist_endpoint(self):
        resp = auth(self.manager).get(f'{BASE}checklist/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('forbidden', resp.data)

    def test_policy_check_endpoint_records_and_passes(self):
        all_keys = [r['key'] for r in policy.DEFAULT_FORBIDDEN]
        resp = auth(self.manager).post(
            f'{BASE}{self.asset.id}/policy-check/',
            {'confirmed_keys': all_keys}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['is_policy_passed'])
