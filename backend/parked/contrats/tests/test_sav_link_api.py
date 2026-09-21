"""Tests du lien d'un ``Contrat`` vers un contrat de maintenance SAV.

Couvre le champ additif ``sav_contrat_maintenance_id`` (CONTRAT5, puis
validation cross-app XCTR13) :
- il est OPTIONNEL et NULL par défaut (la création d'un contrat sans lui marche
  toujours — comportement existant préservé) ;
- il accepte et PERSISTE un id quand il référence un ``sav.ContratMaintenance``
  réel de la MÊME société (validé via ``sav.selectors.contrat_maintenance_
  existe`` depuis XCTR13 — un id arbitraire/inexistant est refusé, voir
  ``test_unification_sav.py``) ;
- il est modifiable via PATCH (mise à jour d'un contrat existant) ;
- la société reste posée côté serveur et l'isolation entre sociétés est intacte.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Contrat
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance

User = get_user_model()


def make_contrat_maintenance(company):
    cli = Client.objects.create(company=company, nom='Client CM')
    return ContratMaintenance.objects.create(
        company=company, client=cli, periodicite='mensuel',
        date_debut=date(2026, 1, 1), prix=600, actif=True,
        facturation_active=True)


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
        # An id referencing a REAL sav.ContratMaintenance in the same company
        # is accepted and persisted (XCTR13 validated linking).
        cm = make_contrat_maintenance(self.co_a)
        api = auth(self.user_a)
        resp = api.post(
            self.BASE,
            {'objet': 'Contrat O&M lié SAV',
             'sav_contrat_maintenance_id': cm.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['sav_contrat_maintenance_id'], cm.id)
        obj = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.sav_contrat_maintenance_id, cm.id)
        # Company is still forced server-side.
        self.assertEqual(obj.company, self.co_a)

    def test_patch_updates_link(self):
        # Updating an existing contract still works and can set/clear the link.
        cm = make_contrat_maintenance(self.co_a)
        contrat = Contrat.objects.create(company=self.co_a, objet='Contrat A')
        api = auth(self.user_a)
        url = f'{self.BASE}{contrat.id}/'
        resp = api.patch(
            url, {'sav_contrat_maintenance_id': cm.id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertEqual(contrat.sav_contrat_maintenance_id, cm.id)
        # And it can be cleared back to NULL.
        resp = api.patch(
            url, {'sav_contrat_maintenance_id': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        self.assertIsNone(contrat.sav_contrat_maintenance_id)

    def test_company_isolation_intact(self):
        # A contract carrying the link stays invisible to another company.
        cm = make_contrat_maintenance(self.co_a)
        Contrat.objects.create(
            company=self.co_a, objet='Contrat A',
            sav_contrat_maintenance_id=cm.id)
        resp = auth(self.user_b).get(self.BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)
