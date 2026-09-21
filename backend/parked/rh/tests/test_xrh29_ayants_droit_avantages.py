"""Tests XRH29 — Ayants droit & avantages sociaux.

Couvre :
* CRUD company-scopé des ayants droit et avantages sociaux ;
* la fiche employé affiche les compteurs de couverture ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import AvantageSocial, AyantDroit, DossierEmploye

User = get_user_model()

AYANTS_DROIT_URL = '/api/django/rh/ayants-droit/'
AVANTAGES_URL = '/api/django/rh/avantages-sociaux/'
EMPLOYES_URL = '/api/django/rh/employes/'


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


class AyantsDroitAvantagesTests(TestCase):
    def setUp(self):
        self.co = make_company('ayd-a', 'A')
        self.rh = make_user(self.co, 'ayd-rh')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='N', prenom='P',
            nombre_enfants=2)

    def test_crud_ayant_droit_company_scope(self):
        resp = auth(self.rh).post(AYANTS_DROIT_URL, {
            'employe': self.dossier.id, 'lien': 'enfant',
            'nom': 'Fils Untel', 'date_naissance': '2015-01-01',
            'couvert_amo': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['couvert_amo'])

        resp = auth(self.rh).get(AYANTS_DROIT_URL, {'employe': self.dossier.id})
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(len(rows), 1)

    def test_crud_avantage_social_company_scope(self):
        resp = auth(self.rh).post(AVANTAGES_URL, {
            'employe': self.dossier.id, 'type': 'mutuelle',
            'organisme': 'CNIA', 'date_adhesion': '2024-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['organisme'], 'CNIA')

    def test_fiche_employe_affiche_compteurs(self):
        AyantDroit.objects.create(
            company=self.co, employe=self.dossier, lien='enfant', nom='A')
        AyantDroit.objects.create(
            company=self.co, employe=self.dossier, lien='conjoint', nom='B')
        AvantageSocial.objects.create(
            company=self.co, employe=self.dossier, type='cimr')

        resp = auth(self.rh).get(f'{EMPLOYES_URL}{self.dossier.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nombre_ayants_droit'], 2)
        self.assertEqual(resp.data['nombre_avantages_sociaux'], 1)
        # Cohérence informative avec nombre_enfants (pas une contrainte dure).
        self.assertEqual(resp.data['nombre_enfants'], 2)

    def test_isolation_societe(self):
        co_b = make_company('ayd-b', 'B')
        rh_b = make_user(co_b, 'ayd-rh-b')
        AyantDroit.objects.create(
            company=self.co, employe=self.dossier, lien='enfant', nom='A')
        resp = auth(rh_b).get(AYANTS_DROIT_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(len(rows), 0)

    def test_employe_autre_societe_rejete(self):
        co_b = make_company('ayd-c', 'B')
        dossier_b = DossierEmploye.objects.create(
            company=co_b, matricule='EB1', nom='N', prenom='P')
        resp = auth(self.rh).post(AYANTS_DROIT_URL, {
            'employe': dossier_b.id, 'lien': 'enfant', 'nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
