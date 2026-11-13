"""ENG7 — Tests de la colonne vertébrale propose→approuve→applique.

Couvre le cycle de vie complet (propose/approve/reject/apply/échec) et
l'INVARIANT DE SÉCURITÉ central : une action non approuvée n'atteint JAMAIS le
client Meta. Gating API : proposer = ``adsengine_manage`` ; approuver/appliquer =
``adsengine_approve`` (permission distincte).
"""
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.models import EngineAction

User = get_user_model()

BASE = '/api/django/adsengine/actions/'
CAMPAIGN_PAYLOAD = {'name': 'Solaire', 'objective': 'OUTCOME_LEADS'}


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


class EngineActionServiceTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EA Co', slug='ea-co')
        self.user = make_user(self.company, 'approver', ['adsengine_approve'])

    def _propose(self):
        return services.propose_action(
            self.company, kind=EngineAction.Kind.CREATE_CAMPAIGN,
            reason_fr="Lancer une campagne leads résidentiel à Casablanca.",
            payload=dict(CAMPAIGN_PAYLOAD))

    def test_propose_creates_proposed_action(self):
        action = self._propose()
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)
        self.assertFalse(action.auto)
        self.assertTrue(action.reason_fr)

    def test_propose_requires_reason(self):
        with self.assertRaises(ValueError):
            services.propose_action(
                self.company, kind=EngineAction.Kind.CREATE_CAMPAIGN,
                reason_fr='   ')

    def test_approve_then_apply_reaches_client(self):
        action = self._propose()
        services.approve_action(action, user=self.user)
        self.assertEqual(action.status, EngineAction.Statut.APPROUVEE)
        self.assertEqual(action.approved_by, self.user)

        client = Mock()
        client.create_campaign.return_value = {'id': '123'}
        services.apply_action(action, client=client)

        client.create_campaign.assert_called_once()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.APPLIQUEE)
        self.assertIsNotNone(action.applied_at)
        self.assertEqual(action.result, {'id': '123'})
        self.assertEqual(action.error, '')

    def test_reject_blocks_apply(self):
        action = self._propose()
        services.reject_action(action, user=self.user, commentaire='Hors budget')
        self.assertEqual(action.status, EngineAction.Statut.REJETEE)

        client = Mock()
        with self.assertRaises(services.ActionNotApproved):
            services.apply_action(action, client=client)
        client.create_campaign.assert_not_called()

    def test_unapproved_action_never_reaches_client(self):
        # INVARIANT DE SÉCURITÉ : une action PROPOSÉE (non approuvée) ne touche
        # jamais le client, même si un client est fourni.
        action = self._propose()
        client = Mock()
        with self.assertRaises(services.ActionNotApproved):
            services.apply_action(action, client=client)
        client.create_campaign.assert_not_called()
        client.create_adset.assert_not_called()
        client.create_ad.assert_not_called()
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.PROPOSEE)

    def test_apply_failure_marks_echouee_and_reraises(self):
        action = self._propose()
        services.approve_action(action, user=self.user)
        client = Mock()
        client.create_campaign.side_effect = RuntimeError('Token expiré')
        with self.assertRaises(RuntimeError):
            services.apply_action(action, client=client)
        action.refresh_from_db()
        self.assertEqual(action.status, EngineAction.Statut.ECHOUEE)
        self.assertIn('Token expiré', action.error)

    def test_cannot_approve_non_proposed(self):
        action = self._propose()
        services.approve_action(action, user=self.user)
        with self.assertRaises(ValueError):
            services.approve_action(action, user=self.user)

    def test_double_apply_is_blocked(self):
        # Une action déjà appliquée n'est plus « approuvee » → ne se rejoue pas.
        action = self._propose()
        services.approve_action(action, user=self.user)
        client = Mock()
        client.create_campaign.return_value = {'id': '1'}
        services.apply_action(action, client=client)
        client.create_campaign.reset_mock()
        with self.assertRaises(services.ActionNotApproved):
            services.apply_action(action, client=client)
        client.create_campaign.assert_not_called()


class EngineActionApiGatingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='EA API', slug='ea-api')
        self.manager = make_user(
            self.company, 'manager', ['adsengine_view', 'adsengine_manage'])
        self.approver = make_user(
            self.company, 'boss',
            ['adsengine_view', 'adsengine_manage', 'adsengine_approve'])

    def _propose_via_api(self, user):
        return auth(user).post(BASE, {
            'kind': 'create_campaign',
            'reason_fr': "Lancer une campagne leads à Rabat.",
            'payload': CAMPAIGN_PAYLOAD,
        }, format='json')

    def test_propose_requires_manage(self):
        viewer = make_user(self.company, 'viewer', ['adsengine_view'])
        self.assertEqual(self._propose_via_api(viewer).status_code, 403)
        resp = self._propose_via_api(self.manager)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['status'], 'proposee')

    def test_reason_required_via_api(self):
        resp = auth(self.manager).post(BASE, {
            'kind': 'create_campaign', 'reason_fr': '',
            'payload': CAMPAIGN_PAYLOAD}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_approve_needs_approve_permission_not_just_manage(self):
        action_id = self._propose_via_api(self.manager).data['id']
        # Le manager (sans adsengine_approve) NE peut PAS approuver.
        denied = auth(self.manager).post(f'{BASE}{action_id}/approve/')
        self.assertEqual(denied.status_code, 403)
        # L'approbateur, oui.
        ok = auth(self.approver).post(f'{BASE}{action_id}/approve/')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(ok.data['status'], 'approuvee')

    def test_status_cannot_be_patched_directly(self):
        action_id = self._propose_via_api(self.manager).data['id']
        auth(self.manager).patch(
            f'{BASE}{action_id}/', {'status': 'approuvee'}, format='json')
        self.assertEqual(
            EngineAction.objects.get(id=action_id).status, 'proposee')
