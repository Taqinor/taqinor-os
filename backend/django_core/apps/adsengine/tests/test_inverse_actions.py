"""PUB45 — « Annuler » une action appliquée = PROPOSER son inverse via le circuit
propose→approuve normal (jamais un write direct). Rétablit une valeur mémorisée
(budget / texte / plafond / nom) ; kinds non inversibles → explication FR.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import EngineAction

User = get_user_model()


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


def applied(company, kind, payload):
    return EngineAction.objects.create(
        company=company, kind=kind, payload=payload,
        reason_fr='Action appliquée.', status=EngineAction.Statut.APPLIQUEE)


class ProposeInverseUnitTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Inv Co', slug='inv-co')

    def test_budget_inverse_restores_previous_budget(self):
        action = applied(
            self.company, EngineAction.Kind.REBALANCE_BUDGET,
            {'adset_id': 'as1', 'daily_budget': 30000, 'current_budget': 20000})
        inverse = services.propose_inverse_action(action)
        self.assertEqual(inverse.status, EngineAction.Statut.PROPOSEE)
        self.assertEqual(inverse.kind, EngineAction.Kind.REBALANCE_BUDGET)
        self.assertEqual(inverse.payload['daily_budget'], 20000)
        self.assertEqual(inverse.payload['inverse_of'], action.pk)
        self.assertEqual(inverse.company_id, self.company.id)

    def test_edit_copy_inverse_restores_previous_creative(self):
        action = applied(
            self.company, EngineAction.Kind.EDIT_COPY,
            {'ad_id': 'ad1',
             'current_creative': {'body': 'ancien texte'},
             'creative_spec': {'body': 'nouveau texte'}})
        inverse = services.propose_inverse_action(action)
        self.assertEqual(inverse.payload['creative_spec'], {'body': 'ancien texte'})

    def test_set_spend_cap_inverse_needs_remembered_value(self):
        # Sans previous_spend_cap → non inversible (valeur non mémorisée).
        action = applied(
            self.company, EngineAction.Kind.SET_SPEND_CAP,
            {'campaign_id': 'c1', 'spend_cap': 500000})
        with self.assertRaises(services.ActionNotInvertible):
            services.propose_inverse_action(action)
        # Avec la valeur précédente mémorisée → inverse.
        action2 = applied(
            self.company, EngineAction.Kind.SET_SPEND_CAP,
            {'campaign_id': 'c1', 'spend_cap': 500000, 'previous_spend_cap': 300000})
        inverse = services.propose_inverse_action(action2)
        self.assertEqual(inverse.payload['spend_cap'], 300000)

    def test_create_kind_is_not_invertible(self):
        action = applied(
            self.company, EngineAction.Kind.CREATE_CAMPAIGN, {'name': 'X'})
        with self.assertRaises(services.ActionNotInvertible):
            services.propose_inverse_action(action)

    def test_pause_is_not_invertible(self):
        action = applied(
            self.company, EngineAction.Kind.PAUSE,
            {'target_meta_id': 'x', 'target_type': 'campaign'})
        with self.assertRaises(services.ActionNotInvertible):
            services.propose_inverse_action(action)

    def test_only_applied_actions_are_invertible(self):
        proposed = EngineAction.objects.create(
            company=self.company, kind=EngineAction.Kind.REBALANCE_BUDGET,
            payload={'adset_id': 'as1', 'daily_budget': 30000, 'current_budget': 20000},
            reason_fr='x', status=EngineAction.Statut.PROPOSEE)
        with self.assertRaises(services.ActionNotInvertible):
            services.propose_inverse_action(proposed)


class AnnulerApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ann Co', slug='ann-co')
        self.manager = make_user(
            self.company, 'mgr', ['adsengine_view', 'adsengine_manage'])
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def _url(self, action):
        return f'/api/django/adsengine/actions/{action.pk}/annuler/'

    def test_budget_cancel_creates_inverse_proposal(self):
        action = applied(
            self.company, EngineAction.Kind.REBALANCE_BUDGET,
            {'adset_id': 'as1', 'daily_budget': 30000, 'current_budget': 20000})
        resp = auth(self.manager).post(self._url(action))
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['status'], EngineAction.Statut.PROPOSEE)
        self.assertEqual(resp.data['payload']['daily_budget'], 20000)
        # Une NOUVELLE action proposée existe (l'inverse) — pas d'écriture directe.
        self.assertEqual(
            EngineAction.objects.filter(
                company=self.company,
                status=EngineAction.Statut.PROPOSEE).count(), 1)

    def test_non_invertible_returns_422_with_explanation(self):
        action = applied(
            self.company, EngineAction.Kind.CREATE_CAMPAIGN, {'name': 'X'})
        resp = auth(self.manager).post(self._url(action))
        self.assertEqual(resp.status_code, 422, resp.data)
        self.assertFalse(resp.data['invertible'])
        self.assertIn('création', resp.data['detail'].lower())

    def test_requires_manage_permission(self):
        action = applied(
            self.company, EngineAction.Kind.REBALANCE_BUDGET,
            {'adset_id': 'as1', 'daily_budget': 30000, 'current_budget': 20000})
        self.assertEqual(auth(self.viewer).post(self._url(action)).status_code, 403)

    def test_other_company_action_is_404(self):
        other = Company.objects.create(nom='Autre', slug='autre-ann')
        foreign = applied(
            other, EngineAction.Kind.REBALANCE_BUDGET,
            {'adset_id': 'as1', 'daily_budget': 30000, 'current_budget': 20000})
        self.assertEqual(auth(self.manager).post(self._url(foreign)).status_code, 404)
