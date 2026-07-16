"""ENG12 — Tests de l'endpoint santé du câblage.

Invariant central : l'endpoint rapporte la seule PRÉSENCE des clés/tokens, JAMAIS
leur valeur (test de non-fuite avec un secret distinctif). Company-scopé + gaté
par ``adsengine_view``.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from apps.adsengine.models import MetaConnection

User = get_user_model()
URL = '/api/django/adsengine/wiring-health/'
SECRET = 'tok-73951-distinctive'


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


class WiringHealthTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='WH Co', slug='wh-co')
        self.viewer = make_user(self.company, 'viewer', ['adsengine_view'])

    def test_reports_key_presence_booleans(self):
        resp = auth(self.viewer).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('keys', resp.data)
        for name, present in resp.data['keys'].items():
            self.assertIsInstance(present, bool)

    def test_requires_view_permission(self):
        nobody = make_user(self.company, 'nobody', [])
        self.assertEqual(auth(nobody).get(URL).status_code, 403)

    def test_connection_presence_never_leaks_token(self):
        MetaConnection.objects.create(
            company=self.company, enabled=True,
            credentials={'access_token': SECRET}, ad_account_id='act_1')
        resp = auth(self.viewer).get(URL)
        body = json.dumps(resp.data)
        # Le token distinctif ne doit APPARAÎTRE nulle part dans la réponse.
        self.assertNotIn(SECRET, body)
        # Seule la présence est rapportée.
        self.assertTrue(resp.data['connection']['has_token'])
        self.assertTrue(resp.data['connection']['enabled'])

    def test_env_secret_value_never_leaks(self):
        # Une clé d'environnement posée à un secret distinctif : l'endpoint ne
        # rapporte que True (présence), jamais la valeur.
        import os
        os.environ['FAL_API_KEY'] = SECRET
        try:
            resp = auth(self.viewer).get(URL)
        finally:
            del os.environ['FAL_API_KEY']
        body = json.dumps(resp.data)
        self.assertNotIn(SECRET, body)
        self.assertTrue(resp.data['keys']['FAL_API_KEY'])
