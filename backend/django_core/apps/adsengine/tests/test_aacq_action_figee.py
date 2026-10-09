"""AACQ1 — Une action du moteur est FIGÉE dès sa proposition.

Plus aucun PUT / PATCH / DELETE sur ``/api/django/adsengine/actions/<id>/`` :
le contenu approuvé est exactement celui qui part chez Meta, et une action
appliquée ne peut plus être réécrite ni supprimée du Journal d'actions. La
proposition (POST) et les gestes dédiés (approve/reject/apply…) restent
inchangés. Seul le client Meta est simulé (``Mock(spec=MetaClient)``).
"""
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine import services
from apps.adsengine.meta_client import MetaClient
from apps.adsengine.models import EngineAction

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


class ActionFigeeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Figee', slug='aacq1-figee')
        self.proposeur = make_user(
            self.company, 'aacq1-commercial',
            ['adsengine_view', 'adsengine_manage'])
        self.approbateur = make_user(
            self.company, 'aacq1-admin',
            ['adsengine_view', 'adsengine_manage', 'adsengine_approve'])
        self.api = auth(self.proposeur)

    def _proposer(self, kind, payload, reason='Raison initiale.'):
        resp = self.api.post(BASE, {
            'kind': kind, 'reason_fr': reason, 'payload': payload,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return EngineAction.objects.get(pk=resp.data['id'])

    def _approuvee_spend_cap(self):
        action = self._proposer(
            EngineAction.Kind.SET_SPEND_CAP,
            {'campaign_id': 'c1', 'spend_cap': 5000})
        services.approve_action(action, user=self.approbateur)
        action.refresh_from_db()
        return action

    def _etat(self, action):
        action.refresh_from_db()
        return (action.kind, action.payload, action.reason_fr,
                action.status, action.approved_by_id)

    def test_patch_payload_apres_approbation_refuse(self):
        action = self._approuvee_spend_cap()
        avant = self._etat(action)
        resp = self.api.patch(f'{BASE}{action.pk}/', {
            'payload': {'campaign_id': 'c1', 'spend_cap': 1000000},
        }, format='json')
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(self._etat(action), avant)

    def test_patch_kind_refuse(self):
        action = self._approuvee_spend_cap()
        avant = self._etat(action)
        resp = self.api.patch(f'{BASE}{action.pk}/', {
            'kind': 'edit_copy', 'payload': {'ad_id': 'a1', 'message': 'x'},
        }, format='json')
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(self._etat(action), avant)

    def test_put_contourne_pub22_refuse(self):
        action = self._approuvee_spend_cap()
        avant = self._etat(action)
        resp = self.api.put(f'{BASE}{action.pk}/', {
            'kind': 'set_spend_cap', 'reason_fr': 'Plafond.',
            'payload': {'campaign_id': 'c1', 'spend_cap': 0},
        }, format='json')
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(self._etat(action), avant)

    def test_delete_action_appliquee_refuse(self):
        action = self._proposer(
            EngineAction.Kind.RENAME, {'object_id': '120999', 'name': 'Nom'})
        EngineAction.objects.filter(pk=action.pk).update(
            status=EngineAction.Statut.APPLIQUEE)
        resp = self.api.delete(f'{BASE}{action.pk}/')
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(EngineAction.objects.filter(pk=action.pk).exists())

    def test_journal_non_reecrit(self):
        action = self._proposer(
            EngineAction.Kind.RENAME, {'object_id': '120999', 'name': 'Nom'})
        EngineAction.objects.filter(pk=action.pk).update(
            status=EngineAction.Statut.APPLIQUEE)
        resp = self.api.patch(f'{BASE}{action.pk}/', {
            'reason_fr': 'Journal reecrit'}, format='json')
        self.assertEqual(resp.status_code, 405)
        action.refresh_from_db()
        self.assertEqual(action.reason_fr, 'Raison initiale.')
        # Lecture du journal inchangée.
        lecture = self.api.get(f'{BASE}{action.pk}/')
        self.assertEqual(lecture.status_code, 200)

    def test_apply_envoie_payload_approuve(self):
        action = self._proposer(
            EngineAction.Kind.RENAME,
            {'object_id': '120999', 'name': 'NOM APPROUVE'})
        services.approve_action(action, user=self.approbateur)
        resp = self.api.patch(f'{BASE}{action.pk}/', {
            'payload': {'object_id': '120999',
                        'name': 'NOM JAMAIS APPROUVE'}}, format='json')
        self.assertEqual(resp.status_code, 405)
        action.refresh_from_db()
        client = Mock(spec=MetaClient)
        client.rename_object.return_value = {'success': True}
        services.apply_action(action, client=client)
        client.rename_object.assert_called_once()
        kwargs = client.rename_object.call_args.kwargs
        self.assertEqual(kwargs['object_id'], '120999')
        self.assertEqual(kwargs['name'], 'NOM APPROUVE')
