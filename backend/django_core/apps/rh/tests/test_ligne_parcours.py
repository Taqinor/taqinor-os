"""Tests ZRH15 — types de ligne de CV / parcours (timeline expérience/
formation).

Couvre : ajout de lignes de types différents triées par date sur la fiche,
types configurables par société, annuaire n'expose pas de champ sensible,
isolation tenant.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, LigneParcours, TypeLigneParcours

User = get_user_model()

URL_TYPES = '/api/django/rh/types-ligne-parcours/'
URL_LIGNES = '/api/django/rh/lignes-parcours/'
URL_ANNUAIRE = '/api/django/rh/employes/annuaire/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LigneParcoursTests(TestCase):
    def setUp(self):
        self.co_a = make_company('lp-a', 'A')
        self.co_b = make_company('lp-b', 'B')
        self.user_a = make_user(self.co_a, 'lp-user-a')
        self.user_b = make_user(self.co_b, 'lp-user-b')
        self.type_exp = TypeLigneParcours.objects.create(
            company=self.co_a, libelle='Expérience', ordre=1)
        self.type_form = TypeLigneParcours.objects.create(
            company=self.co_a, libelle='Formation', ordre=2)
        self.emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='LP1', nom='N', prenom='P')

    def test_ajout_lignes_types_differents_tri_date(self):
        LigneParcours.objects.create(
            company=self.co_a, employe=self.emp, type=self.type_exp,
            intitule='Technicien chez X', date_debut=date(2018, 1, 1))
        LigneParcours.objects.create(
            company=self.co_a, employe=self.emp, type=self.type_form,
            intitule='BTS Électrotechnique', date_debut=date(2022, 1, 1))
        resp = auth(self.user_a).get(URL_LIGNES, {'employe': self.emp.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(len(rows), 2)
        # Trié par date décroissante (plus récent d'abord).
        self.assertEqual(rows[0]['intitule'], 'BTS Électrotechnique')

    def test_types_configurables_par_societe(self):
        resp = auth(self.user_a).get(URL_TYPES)
        libs = [t['libelle'] for t in (
            resp.data['results'] if isinstance(resp.data, dict)
            else resp.data)]
        self.assertIn('Expérience', libs)
        self.assertIn('Formation', libs)

    def test_annuaire_expose_lignes_parcours_sans_sensible(self):
        LigneParcours.objects.create(
            company=self.co_a, employe=self.emp, type=self.type_exp,
            intitule='Poseur solaire')
        resp = auth(self.user_a).get(URL_ANNUAIRE)
        entry = next(e for e in resp.data if e['id'] == self.emp.id)
        self.assertIn('lignes_parcours', entry)
        self.assertEqual(
            entry['lignes_parcours'][0]['intitule'], 'Poseur solaire')
        for ligne in entry['lignes_parcours']:
            self.assertNotIn('salaire', ligne)
            self.assertNotIn('cin', ligne)

    def test_isolation_tenant(self):
        LigneParcours.objects.create(
            company=self.co_a, employe=self.emp, type=self.type_exp,
            intitule='Secret')
        resp = auth(self.user_b).get(URL_LIGNES)
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(len(rows), 0)
