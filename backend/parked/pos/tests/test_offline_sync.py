"""NTRET1 — Mode offline caisse : dédup serveur sur ``uuid_client``.

Une vente comptoir créée sans réseau reçoit un ``uuid_client`` généré côté
navigateur (frontend/src/features/pos/offlineQueue.js) et est rejouée contre
``POST /api/django/pos/ventes/`` dès la reconnexion. Un rejeu en double (même
uuid_client, ex. réponse réseau perdue puis file rejouée deux fois) ne doit
JAMAIS créer une deuxième ``VenteComptoir`` — couvert ici au niveau API et au
niveau selector, + isolation multi-tenant (le même uuid_client peut être
utilisé par deux sociétés différentes sans collision).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.pos import selectors
from apps.pos.models import VenteComptoir

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class OfflineSyncDedupApiTests(TestCase):
    BASE = '/api/django/pos/ventes/'

    def setUp(self):
        self.co = make_company('ntret1', 'NTRET1 Co')
        self.user = make_user(self.co, 'ntret1-user')

    def test_replay_same_uuid_client_does_not_duplicate(self):
        api = auth(self.user)
        payload = {'uuid_client': 'offline-uuid-0001'}

        first = api.post(self.BASE, payload, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        second = api.post(self.BASE, payload, format='json')
        self.assertEqual(second.status_code, 201, second.data)

        # Même vente renvoyée les deux fois — jamais un doublon.
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(
            VenteComptoir.objects.filter(
                company=self.co, uuid_client='offline-uuid-0001').count(),
            1,
        )

    def test_different_uuid_client_creates_distinct_ventes(self):
        api = auth(self.user)
        first = api.post(
            self.BASE, {'uuid_client': 'offline-uuid-a'}, format='json')
        second = api.post(
            self.BASE, {'uuid_client': 'offline-uuid-b'}, format='json')
        self.assertNotEqual(first.data['id'], second.data['id'])

    def test_no_uuid_client_never_dedupes(self):
        """Une vente créée EN LIGNE (sans uuid_client) garde le comportement
        historique : chaque POST crée une nouvelle vente."""
        api = auth(self.user)
        first = api.post(self.BASE, {}, format='json')
        second = api.post(self.BASE, {}, format='json')
        self.assertNotEqual(first.data['id'], second.data['id'])

    def test_uuid_client_isolated_per_company(self):
        """Le MÊME uuid_client peut être réutilisé par deux sociétés
        distinctes sans collision (dédup scoping company, pas global)."""
        co_b = make_company('ntret1-b', 'NTRET1 Co B')
        user_b = make_user(co_b, 'ntret1-b-user')
        api_a = auth(self.user)
        api_b = auth(user_b)

        resp_a = api_a.post(
            self.BASE, {'uuid_client': 'shared-uuid'}, format='json')
        resp_b = api_b.post(
            self.BASE, {'uuid_client': 'shared-uuid'}, format='json')
        self.assertEqual(resp_a.status_code, 201, resp_a.data)
        self.assertEqual(resp_b.status_code, 201, resp_b.data)
        self.assertNotEqual(resp_a.data['id'], resp_b.data['id'])


class OfflineSyncSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret1-sel', 'NTRET1 Selector Co')
        self.user = make_user(self.co, 'ntret1-sel-user')

    def test_vente_par_uuid_client_none_when_absent(self):
        self.assertIsNone(
            selectors.vente_par_uuid_client(self.co, 'introuvable'))

    def test_vente_par_uuid_client_returns_match(self):
        vente = VenteComptoir.objects.create(
            company=self.co, reference='VC-OFF-0001',
            uuid_client='sel-uuid-1', created_by=self.user)
        found = selectors.vente_par_uuid_client(self.co, 'sel-uuid-1')
        self.assertEqual(found.id, vente.id)

    def test_vente_par_uuid_client_blank_returns_none(self):
        self.assertIsNone(selectors.vente_par_uuid_client(self.co, ''))
        self.assertIsNone(selectors.vente_par_uuid_client(self.co, None))
