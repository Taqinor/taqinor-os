"""AANA36 — l'admin gère aussi les clés ``test`` (bac à sable de SA société).

Constat C-AANA-012 : une clé ``environnement='test'`` est émise sur la
société-jumelle du bac à sable (NTAPI26/27) ; l'écran de gestion filtrait
sur la seule société réelle, donc ``keys/<id>/revoke/`` répondait 404 et la
clé restait active. Désormais la liste, la révocation, la rotation et la
suppression couvrent le bac à sable de la société de l'utilisateur — jamais
celui d'une autre société.

Vraies vues de gestion (JWT), vraie authentification par clé, vraie base.

Run :
    python manage.py test apps.publicapi.tests_aana_cles_test -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .constants import ENV_TEST
from .models import ApiKey
from .portees import SCOPE_READ_LEADS

User = get_user_model()

URL_CLES = '/api/django/publicapi/keys/'


def _session(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _cle_api(brute):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {brute}')
    return api


class ClesTestGereesTest(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aana36-a', defaults={'nom': 'AANA36 A'})
        self.autre, _ = Company.objects.get_or_create(
            slug='aana36-b', defaults={'nom': 'AANA36 B'})
        self.admin = User.objects.create_user(
            username='aana36-admin', password='x', company=self.co,
            role_legacy='admin')
        self.admin_b = User.objects.create_user(
            username='aana36-admin-b', password='x', company=self.autre,
            role_legacy='admin')

    def _creer_cle_test(self, admin):
        resp = _session(admin).post(URL_CLES, {
            'label': 'clé de test', 'scopes': [SCOPE_READ_LEADS],
            'environnement': ENV_TEST}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id'], resp.data['key']

    def test_revocation_cle_test(self):
        cle_id, brute = self._creer_cle_test(self.admin)
        self.assertEqual(
            _cle_api(brute).get('/api/public/v1/leads/').status_code, 200)

        resp = _session(self.admin).post(f'{URL_CLES}{cle_id}/revoke/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ApiKey.objects.get(pk=cle_id).enabled)
        refus = _cle_api(brute).get('/api/public/v1/leads/')
        self.assertIn(refus.status_code, (401, 403))

    def test_la_cle_test_est_listee(self):
        cle_id, _brute = self._creer_cle_test(self.admin)
        resp = _session(self.admin).get(URL_CLES)
        self.assertEqual(resp.status_code, 200)
        lignes = resp.data['results'] if isinstance(resp.data, dict) \
            and 'results' in resp.data else resp.data
        self.assertIn(cle_id, [ligne['id'] for ligne in lignes])

    def test_rotation_et_suppression_cle_test(self):
        cle_id, _brute = self._creer_cle_test(self.admin)
        rotation = _session(self.admin).post(f'{URL_CLES}{cle_id}/rotate/')
        self.assertEqual(rotation.status_code, 201)
        suppression = _session(self.admin).delete(f'{URL_CLES}{cle_id}/')
        self.assertEqual(suppression.status_code, 204)
        self.assertFalse(ApiKey.objects.filter(pk=cle_id).exists())

    def test_bac_a_sable_d_une_autre_societe_404(self):
        cle_b, brute_b = self._creer_cle_test(self.admin_b)
        session = _session(self.admin)
        self.assertEqual(
            session.post(f'{URL_CLES}{cle_b}/revoke/').status_code, 404)
        self.assertEqual(session.delete(f'{URL_CLES}{cle_b}/').status_code, 404)
        self.assertTrue(ApiKey.objects.get(pk=cle_b).enabled)
        lignes = session.get(URL_CLES).data
        lignes = lignes['results'] if isinstance(lignes, dict) \
            and 'results' in lignes else lignes
        self.assertNotIn(cle_b, [ligne['id'] for ligne in lignes])
