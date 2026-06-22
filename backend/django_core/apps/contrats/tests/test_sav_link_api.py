"""Tests du lien LÂCHE d'un ``Contrat`` vers un contrat de maintenance SAV.

Couvre le champ additif ``sav_contrat_maintenance_id`` (CONTRAT5) :
- il est OPTIONNEL et NULL par défaut (la création d'un contrat sans lui marche
  toujours — comportement existant préservé) ;
- il accepte et PERSISTE un id quand il est fourni à la création ;
- il est modifiable via PATCH (mise à jour d'un contrat existant) ;
- il est STOCKÉ tel quel sans validation cross-app (aucun ``sav.ContratMaintenance``
  réel requis — l'app ``sav`` n'expose pas de ``selectors.py``) ;
- la société reste posée côté serveur et l'isolation entre sociétés est intacte.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Contrat

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ContratSavMaintenanceLinkTests(TestCase):
    BASE = '/api/django/contrats/contrats/'

    def setUp(self):
        self.co_a = make_company('contrat-sav-a', 'A')
        self.co_b = make_company('contrat-sav-b', 'B')
        self.user_a = make_user(self.co_a, 'contrat-sav-a')
        self.user_b = make_user(self.co_b, 'contrat-sav-b')

    def test_field_optional_defaults_null(self):
        # Existing behaviour preserved: a contract created without the field is
        # fine and the link is NULL by default.
        api = auth(self.user_a)
        resp = api.post(
            self.BASE, {'objet': 'Contrat O&M sans lien SAV'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('sav_contrat_maintenance_id', resp.data)
        self.assertIsNone(resp.data['sav_contrat_maintenance_id'])
        obj = Contrat.objects.get(id=resp.data['id'])
        self.assertIsNone(obj.sav_contrat_maintenance_id)

    def test_create_persists_provided_id(self):
        # The id is stored as-is, with NO cross-app validation (no real
        # sav.ContratMaintenance needs to exist).
        api = auth(self.user_a)
        resp = api.post(
            self.BASE,
            {'objet': 'Contrat O&M lié SAV',
             'sav_contrat_maintenance_id': 777},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['sav_contrat_maintenance_id'], 777)
        obj = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.sav_contrat_maintenance_id, 777)
        # Company is still forced server-side.
        self.assertEqual(obj.company, self.co_a)

    def test_patch_updates_link(self):
        # Updating an existing contract still works and can set/clear the link.
        contrat = Contrat.objects.create(company=self.co_a, objet='Contrat A')
        api = auth(self.user_a)
        url = f'{self.BASE}{contrat.id}/'
        resp = api.patch(
            url, {'sav_contrat_maintenance_id': 42}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.sav_contrat_maintenance_id, 42)
        # And it can be cleared back to NULL.
        resp = api.patch(
            url, {'sav_contrat_maintenance_id': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertIsNone(contrat.sav_contrat_maintenance_id)

    def test_company_isolation_intact(self):
        # A contract carrying the link stays invisible to another company.
        Contrat.objects.create(
            company=self.co_a, objet='Contrat A',
            sav_contrat_maintenance_id=5)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)
