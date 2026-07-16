"""ENG2 — Tests de ``MetaConnection`` (connexion Meta par société).

Invariants prouvés :
  - ``credentials`` est write-only : une fois écrit, un GET ne le renvoie
    JAMAIS (aucun secret ne fuit) — on cherche un secret DISTINCTIF (73951)
    dans TOUTE réponse GET ;
  - ``company`` est posée côté serveur (jamais lue du corps) — un POST qui tente
    d'imposer une autre société est ignoré ;
  - isolation multi-tenant : la société B ne voit pas la connexion de A ;
  - ``has_credentials`` expose seulement la PRÉSENCE du secret.
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

# Secret distinctif à 5 chiffres — ne collisionne pas avec un PK/horodatage.
SECRET = 'tok-73951-secret'
NEEDLE = '73951'

BASE = '/api/django/adsengine/connexions/'


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


class MetaConnectionSecretTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Ads A', slug='ads-a')
        self.user = make_user(
            self.company, 'ads_manager',
            ['adsengine_view', 'adsengine_manage'])

    def test_create_then_get_never_leaks_credentials(self):
        api = auth(self.user)
        resp = api.post(BASE, {
            'enabled': True,
            'ad_account_id': 'act_123',
            'credentials': {'access_token': SECRET},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # La réponse de création ne renvoie PAS le secret (write-only).
        self.assertNotIn(NEEDLE, json.dumps(resp.data))
        self.assertTrue(resp.data['has_credentials'])

        conn_id = resp.data['id']
        # ... mais il a bien été persisté côté serveur.
        conn = MetaConnection.objects.get(id=conn_id)
        self.assertEqual(conn.credentials.get('access_token'), SECRET)

        # Un GET détail ne fuit AUCUN secret.
        detail = api.get(f'{BASE}{conn_id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertNotIn(NEEDLE, json.dumps(detail.data))
        self.assertTrue(detail.data['has_credentials'])
        self.assertNotIn('credentials', detail.data)

        # Un GET liste ne fuit AUCUN secret non plus.
        listing = api.get(BASE)
        self.assertEqual(listing.status_code, 200)
        self.assertNotIn(NEEDLE, json.dumps(listing.data))

    def test_company_is_forced_server_side(self):
        other = Company.objects.create(nom='Ads B', slug='ads-b')
        api = auth(self.user)
        resp = api.post(BASE, {
            'enabled': False,
            'ad_account_id': 'act_forced',
            'company': other.id,  # tentative d'injection — doit être ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        conn = MetaConnection.objects.get(id=resp.data['id'])
        self.assertEqual(conn.company_id, self.company.id)

    def test_tenant_isolation(self):
        # Connexion pour la société A.
        auth(self.user).post(BASE, {
            'enabled': True, 'ad_account_id': 'act_a',
            'credentials': {'access_token': SECRET},
        }, format='json')
        # Société B, autre utilisateur : ne voit RIEN de A.
        company_b = Company.objects.create(nom='Ads C', slug='ads-c')
        user_b = make_user(
            company_b, 'ads_b', ['adsengine_view', 'adsengine_manage'])
        listing = auth(user_b).get(BASE)
        self.assertEqual(rows(listing), [])
