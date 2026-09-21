"""Tests de la matrice des risques P × I (heatmap 5×5) (ZPRJ8).

Couvre : comptage exact par cellule (probabilité, impact) ; les risques
CLOS/MAÎTRISÉS sont EXCLUS de la grille ; un projet sans risque actif renvoie
une grille entièrement à zéro (pas d'erreur) ; top risques trié par
criticité décroissante ; isolation société sur l'endpoint
``projets/<id>/matrice-risques/``.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import Projet, Risque

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


class MatriceRisquesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z8-sel', 'S')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z8', nom='P')

    def test_projet_sans_risque_grille_vide(self):
        data = selectors.matrice_risques(self.projet)
        self.assertEqual(len(data['grille']), 25)
        self.assertTrue(all(cell['nombre'] == 0 for cell in data['grille']))
        self.assertEqual(data['total_ouverts_surveilles'], 0)
        self.assertEqual(data['top_risques'], [])

    def test_comptage_exact_par_cellule(self):
        Risque.objects.create(
            company=self.co, projet=self.projet, libelle='R1',
            probabilite=3, impact=4, statut=Risque.Statut.OUVERT)
        Risque.objects.create(
            company=self.co, projet=self.projet, libelle='R2',
            probabilite=3, impact=4, statut=Risque.Statut.SURVEILLE)
        Risque.objects.create(
            company=self.co, projet=self.projet, libelle='R3',
            probabilite=1, impact=1, statut=Risque.Statut.OUVERT)
        data = selectors.matrice_risques(self.projet)
        cell_3_4 = next(
            c for c in data['grille']
            if c['probabilite'] == 3 and c['impact'] == 4)
        cell_1_1 = next(
            c for c in data['grille']
            if c['probabilite'] == 1 and c['impact'] == 1)
        self.assertEqual(cell_3_4['nombre'], 2)
        self.assertEqual(cell_1_1['nombre'], 1)
        self.assertEqual(data['total_ouverts_surveilles'], 3)

    def test_risques_clos_maitrises_exclus(self):
        Risque.objects.create(
            company=self.co, projet=self.projet, libelle='R-clos',
            probabilite=5, impact=5, statut=Risque.Statut.CLOS)
        Risque.objects.create(
            company=self.co, projet=self.projet, libelle='R-maitrise',
            probabilite=5, impact=5, statut=Risque.Statut.MAITRISE)
        data = selectors.matrice_risques(self.projet)
        cell_5_5 = next(
            c for c in data['grille']
            if c['probabilite'] == 5 and c['impact'] == 5)
        self.assertEqual(cell_5_5['nombre'], 0)
        self.assertEqual(data['total_ouverts_surveilles'], 0)

    def test_top_risques_trie_par_criticite_decroissante(self):
        Risque.objects.create(
            company=self.co, projet=self.projet, libelle='faible',
            probabilite=1, impact=1, statut=Risque.Statut.OUVERT)
        Risque.objects.create(
            company=self.co, projet=self.projet, libelle='fort',
            probabilite=5, impact=5, statut=Risque.Statut.OUVERT)
        data = selectors.matrice_risques(self.projet)
        self.assertEqual(data['top_risques'][0]['libelle'], 'fort')
        self.assertEqual(data['top_risques'][0]['criticite'], 25)
        self.assertEqual(data['top_risques'][1]['libelle'], 'faible')


class MatriceRisquesApiTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co_a = make_company('gp-z8-a', 'A')
        self.co_b = make_company('gp-z8-b', 'B')
        self.user_a = make_user(self.co_a, 'gp-z8-a-u')
        self.user_b = make_user(self.co_b, 'gp-z8-b-u')
        self.projet_a = Projet.objects.create(
            company=self.co_a, code='P-Z8A', nom='A')
        Risque.objects.create(
            company=self.co_a, projet=self.projet_a, libelle='R',
            probabilite=2, impact=3, statut=Risque.Statut.OUVERT)

    def test_endpoint_expose_grille(self):
        api = auth(self.user_a)
        resp = api.get(f'{self.BASE}{self.projet_a.id}/matrice-risques/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('grille', resp.data)
        self.assertEqual(resp.data['total_ouverts_surveilles'], 1)

    def test_isolation_societe_404(self):
        api = auth(self.user_b)
        resp = api.get(f'{self.BASE}{self.projet_a.id}/matrice-risques/')
        self.assertEqual(resp.status_code, 404)
