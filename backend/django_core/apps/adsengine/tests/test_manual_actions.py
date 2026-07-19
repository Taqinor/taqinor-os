"""PUB22 — Composeurs manuels : validation de payload par kind (POST brut) +
endpoint de proposition CURÉE (duplicate / create_ad_study). Toute proposition
naît PROPOSÉE (jamais appliquée), company-scopée, gatée ``adsengine_manage``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import (
    AdCampaignMirror, AdSetMirror, EngineAction)

User = get_user_model()
ACTIONS_URL = '/api/django/adsengine/actions/'


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


class ValidateManualPayloadUnitTests(TestCase):
    """Contrôle pur (sans DB) du trio validé create_ad/set_spend_cap/rename."""

    def test_create_ad_requires_name_and_adset(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.validate_manual_payload(
                EngineAction.Kind.CREATE_AD, {'adset_id': 'as1'})
        with self.assertRaises(services.ActionPayloadInvalid):
            services.validate_manual_payload(
                EngineAction.Kind.CREATE_AD, {'name': 'Ad'})

    def test_set_spend_cap_requires_positive_number(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.validate_manual_payload(
                EngineAction.Kind.SET_SPEND_CAP,
                {'campaign_id': 'c1', 'spend_cap': 0})
        with self.assertRaises(services.ActionPayloadInvalid):
            services.validate_manual_payload(
                EngineAction.Kind.SET_SPEND_CAP,
                {'campaign_id': 'c1', 'spend_cap': 'abc'})

    def test_rename_requires_object_and_name(self):
        with self.assertRaises(services.ActionPayloadInvalid):
            services.validate_manual_payload(
                EngineAction.Kind.RENAME, {'object_id': 'o1'})

    def test_valid_payloads_pass(self):
        services.validate_manual_payload(
            EngineAction.Kind.CREATE_AD, {'name': 'Ad', 'adset_id': 'as1'})
        services.validate_manual_payload(
            EngineAction.Kind.SET_SPEND_CAP,
            {'campaign_id': 'c1', 'spend_cap': 5000})
        services.validate_manual_payload(
            EngineAction.Kind.RENAME, {'object_id': 'o1', 'name': 'x'})

    def test_untracked_kind_is_noop(self):
        # pause / rebalance ont un producteur curé → non soumis à ce contrôle.
        services.validate_manual_payload(EngineAction.Kind.PAUSE, {})


class RawProposeValidationApiTests(TestCase):
    """La validation par kind s'applique au POST BRUT sur /actions/ (perform_create)."""

    def setUp(self):
        self.company = Company.objects.create(nom='MA Co', slug='ma-co')
        self.manager = make_user(
            self.company, 'mgr', ['adsengine_view', 'adsengine_manage'])

    def _post(self, kind, payload):
        return auth(self.manager).post(
            ACTIONS_URL,
            {'kind': kind, 'reason_fr': 'Raison de test.', 'payload': payload},
            format='json')

    def test_create_ad_missing_field_rejected(self):
        resp = self._post('create_ad', {'adset_id': 'as1'})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_set_spend_cap_non_positive_rejected(self):
        resp = self._post('set_spend_cap', {'campaign_id': 'c1', 'spend_cap': 0})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_rename_valid_creates_proposed_action(self):
        resp = self._post('rename', {'object_id': 'o1', 'name': 'Nouveau'})
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(pk=resp.data['id'])
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(action.company_id, self.company.id)

    def test_pause_not_subject_to_trio_validation(self):
        resp = self._post(
            'pause', {'target_meta_id': 'x', 'target_type': 'campaign'})
        self.assertEqual(resp.status_code, 201, resp.data)


class ProposeCuratedApiTests(TestCase):
    """Endpoint actions/proposer/<kind>/ — producteurs curés (duplicate, ad_study)."""

    def setUp(self):
        self.company = Company.objects.create(nom='Cur Co', slug='cur-co')
        self.manager = make_user(
            self.company, 'mgr', ['adsengine_view', 'adsengine_manage'])
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def _url(self, kind):
        return f'/api/django/adsengine/actions/proposer/{kind}/'

    def test_requires_manage_permission(self):
        resp = auth(self.viewer).post(
            self._url('create_ad_study'),
            {'name': 'E', 'cells': [], 'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_create_ad_study_valid_proposes(self):
        resp = auth(self.manager).post(
            self._url('create_ad_study'),
            {'name': 'Étude hooks',
             'cells': [{'name': 'A', 'treatment_percentage': 50},
                       {'name': 'B', 'treatment_percentage': 50}],
             'reason_fr': 'Comparer deux hooks.'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        action = EngineAction.objects.get(pk=resp.data['id'])
        self.assertEqual(action.kind, services.KIND_CREATE_AD_STUDY)
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_create_ad_study_bad_cells_rejected(self):
        resp = auth(self.manager).post(
            self._url('create_ad_study'),
            {'name': 'E',
             'cells': [{'name': 'A', 'treatment_percentage': 100}],
             'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_duplicate_unknown_adset_rejected(self):
        resp = auth(self.manager).post(
            self._url('duplicate'),
            {'adset_id': 'inconnu', 'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_duplicate_without_live_creative_rejected(self):
        campaign = AdCampaignMirror.objects.create(
            company=self.company, meta_id='c1', status='PAUSED')
        AdSetMirror.objects.create(
            company=self.company, meta_id='as1', campaign=campaign)
        resp = auth(self.manager).post(
            self._url('duplicate'),
            {'adset_id': 'as1', 'reason_fr': 'x'}, format='json')
        # Producteur curé : aucun créatif LIVE → ValueError → 400 (jamais 500).
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_unknown_curated_kind_rejected(self):
        resp = auth(self.manager).post(
            self._url('pas_un_kind'), {'reason_fr': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
