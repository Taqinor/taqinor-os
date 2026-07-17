"""NTAPI5 — en-tête `X-Taqinor-Api-Version` épinglé par clé.

Une clé porte `api_version` (défaut 'v1') ; TOUTE réponse (succès ET erreur)
sur une vue publique renvoie cet en-tête, quel que soit le chemin appelé
(aujourd'hui non-versionné — NTAPI1 n'est pas encore construit). Changer de
version reste une action admin explicite (jamais automatique/déduite du
chemin ou du contenu de la requête).
"""
from rest_framework.test import APIClient
from django.test import TestCase

from authentication.models import Company

from .constants import SCOPE_READ_LEADS
from .models import ApiKey
from .public_response import API_VERSION_HEADER


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


class Ntapi5ApiVersionHeaderTests(TestCase):
    def setUp(self):
        self.co = _company('ntapi5', 'NTAPI5')
        self.key, self.raw = ApiKey.issue(
            company=self.co, label='v', scopes=[SCOPE_READ_LEADS])

    def test_default_key_reports_v1_on_success(self):
        self.assertEqual(self.key.api_version, 'v1')
        resp = _key_client(self.raw).get('/api/public/leads/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp[API_VERSION_HEADER], 'v1')

    def test_pinned_version_reported_even_on_error(self):
        # Changement d'épinglage = action admin explicite (jamais dérivée du
        # chemin appelé, qui reste non-versionné aujourd'hui).
        self.key.api_version = 'v2'
        self.key.save(update_fields=['api_version'])
        resp = _key_client(self.raw).get('/api/public/devis/')  # 403 : hors scope
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp[API_VERSION_HEADER], 'v2')

    def test_pinned_version_stable_regardless_of_unversioned_path(self):
        # Le même chemin non-versionné sert la version épinglée à CHAQUE clé,
        # indépendamment l'une de l'autre.
        other_key, other_raw = ApiKey.issue(
            company=self.co, label='other', scopes=[SCOPE_READ_LEADS])
        self.assertEqual(other_key.api_version, 'v1')
        resp_v1 = _key_client(other_raw).get('/api/public/leads/')
        self.assertEqual(resp_v1[API_VERSION_HEADER], 'v1')
        self.key.api_version = 'v2'
        self.key.save(update_fields=['api_version'])
        resp_v2 = _key_client(self.raw).get('/api/public/leads/')
        self.assertEqual(resp_v2[API_VERSION_HEADER], 'v2')
