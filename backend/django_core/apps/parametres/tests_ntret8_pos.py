"""NTRET8 — Paramètres POS dédiés (onglet Paramètres → Point de vente).

Couvre : le taux horaire comptoir se lit/sauvegarde (défaut = NULL,
comportement inchangé), une boutique active référence un EmplacementStock
existant de la MÊME société (jamais un emplacement d'une autre société),
écriture réservée admin/responsable (limité → 403), scoping multi-tenant.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models_pos import BoutiquePos, ParametresPos
from apps.stock.models import EmplacementStock

User = get_user_model()

POS_PARAMS = '/api/django/parametres/pos/'
POS_PARAMS_UPDATE = '/api/django/parametres/pos/update/'
BOUTIQUES = '/api/django/parametres/pos-boutiques/'


def _company(slug='ntret8-co', nom='NTRET8 Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ParametresPosSingletonTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = User.objects.create_user(
            username='ntret8-admin', password='pw', role_legacy='admin',
            company=self.company)
        self.viewer = User.objects.create_user(
            username='ntret8-viewer', password='pw', role_legacy='utilisateur',
            company=self.company)

    def test_default_taux_horaire_is_none(self):
        api = _auth(self.viewer)
        resp = api.get(POS_PARAMS)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['taux_horaire_comptoir'])

    def test_admin_updates_taux_horaire(self):
        api = _auth(self.admin)
        resp = api.patch(
            POS_PARAMS_UPDATE, {'taux_horaire_comptoir': '120.50'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['taux_horaire_comptoir'], '120.50')

        parametres = ParametresPos.objects.get(company=self.company)
        self.assertEqual(parametres.taux_horaire_comptoir, Decimal('120.50'))

    def test_viewer_cannot_update(self):
        api = _auth(self.viewer)
        resp = api.patch(
            POS_PARAMS_UPDATE, {'taux_horaire_comptoir': '99'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_get_creates_singleton_idempotently(self):
        api = _auth(self.admin)
        api.get(POS_PARAMS)
        api.get(POS_PARAMS)
        self.assertEqual(
            ParametresPos.objects.filter(company=self.company).count(), 1)


class BoutiquePosApiTests(TestCase):
    def setUp(self):
        self.co_a = _company('ntret8-a', 'A')
        self.co_b = _company('ntret8-b', 'B')
        self.admin_a = User.objects.create_user(
            username='ntret8-a-admin', password='pw', role_legacy='admin',
            company=self.co_a)
        self.viewer_a = User.objects.create_user(
            username='ntret8-a-viewer', password='pw', role_legacy='utilisateur',
            company=self.co_a)
        self.admin_b = User.objects.create_user(
            username='ntret8-b-admin', password='pw', role_legacy='admin',
            company=self.co_b)
        self.emplacement_a = EmplacementStock.objects.create(
            company=self.co_a, nom='Showroom Casablanca')
        self.emplacement_b = EmplacementStock.objects.create(
            company=self.co_b, nom='Showroom Rabat')

    def test_admin_creates_boutique_for_own_emplacement(self):
        api = _auth(self.admin_a)
        resp = api.post(BOUTIQUES, {
            'emplacement': self.emplacement_a.id,
            'adresse': '12 rue du Solaire',
            'horaires': 'Lun-Sam 9h-19h',
            'surface_m2': '85.5',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['emplacement_nom'], 'Showroom Casablanca')

        boutique = BoutiquePos.objects.get(id=resp.data['id'])
        self.assertEqual(boutique.company_id, self.co_a.id)

    def test_cannot_create_boutique_for_another_company_emplacement(self):
        api = _auth(self.admin_a)
        resp = api.post(BOUTIQUES, {
            'emplacement': self.emplacement_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            BoutiquePos.objects.filter(emplacement=self.emplacement_b).exists())

    def test_viewer_can_list_but_not_create(self):
        api_viewer = _auth(self.viewer_a)
        list_resp = api_viewer.get(BOUTIQUES)
        self.assertEqual(list_resp.status_code, 200, list_resp.data)

        create_resp = api_viewer.post(
            BOUTIQUES, {'emplacement': self.emplacement_a.id}, format='json')
        self.assertEqual(create_resp.status_code, 403)

    def test_isolation_between_companies(self):
        api_a = _auth(self.admin_a)
        api_a.post(BOUTIQUES, {'emplacement': self.emplacement_a.id}, format='json')

        api_b = _auth(self.admin_b)
        resp_b = api_b.get(BOUTIQUES)
        self.assertEqual(resp_b.status_code, 200)
        self.assertEqual(len(resp_b.data.get('results', resp_b.data)), 0)

    def test_default_active_true_default_behavior_unchanged(self):
        api = _auth(self.admin_a)
        resp = api.post(
            BOUTIQUES, {'emplacement': self.emplacement_a.id}, format='json')
        self.assertTrue(resp.data['actif'])
        self.assertIsNone(resp.data['surface_m2'])
