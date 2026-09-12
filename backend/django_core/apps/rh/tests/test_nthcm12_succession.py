"""Tests NTHCM12 — plans de succession par poste-clé.

Couvre :
* marquer un poste critique + assigner 2 successeurs avec readiness ;
* ``couverture/`` signale les postes-clés SANS aucun successeur (orphelin) ;
* CRUD société-scopé (société posée côté serveur, FK d'une autre société
  refusée) ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, PlanSuccession, PosteCle, Poste

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


class SuccessionTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm12-a', 'A')
        self.rh = make_user(self.co, 'nthcm12-rh')
        self.api = auth(self.rh)
        self.poste = Poste.objects.create(
            company=self.co, intitule='Chef de chantier')
        self.poste_orphelin = Poste.objects.create(
            company=self.co, intitule='Responsable QHSE')
        self.s1 = DossierEmploye.objects.create(
            company=self.co, matricule='S-1', nom='Alpha', prenom='Un')
        self.s2 = DossierEmploye.objects.create(
            company=self.co, matricule='S-2', nom='Beta', prenom='Deux')

    def test_marquer_poste_cle_et_assigner_deux_successeurs(self):
        resp = self.api.post(
            '/api/django/rh/postes-cles/',
            {'poste': self.poste.id, 'criticite': 'critique',
             'justification': 'Unique habilitation électrique'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        poste_cle_id = resp.data['id']
        self.assertEqual(
            PosteCle.objects.get(id=poste_cle_id).company_id, self.co.id)

        for successeur, rang, readiness in (
                (self.s1, 'premier', 'pret_immediat'),
                (self.s2, 'second', 'pret_1an')):
            plan = self.api.post(
                '/api/django/rh/plans-succession/',
                {'poste_cle': poste_cle_id, 'successeur': successeur.id,
                 'rang': rang, 'readiness': readiness,
                 'plan_developpement': 'Coaching terrain'}, format='json')
            self.assertEqual(plan.status_code, 201, plan.data)

        couverture = self.api.get(
            f'/api/django/rh/postes-cles/{poste_cle_id}/couverture/')
        self.assertEqual(couverture.status_code, 200, couverture.data)
        self.assertEqual(couverture.data['nombre_successeurs'], 2)
        self.assertEqual(couverture.data['prets_immediat'], 1)
        self.assertFalse(couverture.data['orphelin'])

    def test_poste_cle_sans_successeur_est_orphelin(self):
        poste_cle = PosteCle.objects.create(
            company=self.co, poste=self.poste_orphelin, criticite='haute')
        couverture = selectors.couverture_poste_cle(self.co, poste_cle.id)
        self.assertTrue(couverture['orphelin'])
        self.assertEqual(couverture['nombre_successeurs'], 0)

    def test_couverture_globale_met_les_orphelins_en_tete(self):
        couvert = PosteCle.objects.create(
            company=self.co, poste=self.poste, criticite='critique')
        PlanSuccession.objects.create(
            company=self.co, poste_cle=couvert, successeur=self.s1,
            rang=PlanSuccession.Rang.PREMIER,
            readiness=PlanSuccession.Readiness.PRET_IMMEDIAT)
        PosteCle.objects.create(
            company=self.co, poste=self.poste_orphelin, criticite='haute')
        lignes = selectors.couverture_postes_cles(self.co)
        self.assertEqual(len(lignes), 2)
        self.assertTrue(lignes[0]['orphelin'])
        self.assertFalse(lignes[1]['orphelin'])

    def test_endpoint_couverture_globale(self):
        PosteCle.objects.create(
            company=self.co, poste=self.poste_orphelin, criticite='haute')
        resp = self.api.get('/api/django/rh/postes-cles/couverture/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertTrue(resp.data[0]['orphelin'])

    def test_un_poste_ne_peut_etre_marque_deux_fois(self):
        PosteCle.objects.create(
            company=self.co, poste=self.poste, criticite='haute')
        resp = self.api.post(
            '/api/django/rh/postes-cles/',
            {'poste': self.poste.id, 'criticite': 'critique'},
            format='json')
        self.assertIn(resp.status_code, (400, 409), resp.data)

    def test_poste_autre_societe_refuse(self):
        co_b = make_company('nthcm12-b', 'B')
        poste_b = Poste.objects.create(company=co_b, intitule='Ailleurs')
        resp = self.api.post(
            '/api/django/rh/postes-cles/',
            {'poste': poste_b.id, 'criticite': 'haute'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_successeur_autre_societe_refuse(self):
        poste_cle = PosteCle.objects.create(
            company=self.co, poste=self.poste, criticite='haute')
        co_b = make_company('nthcm12-c', 'C')
        etranger = DossierEmploye.objects.create(
            company=co_b, matricule='X-1', nom='Etranger', prenom='Un')
        resp = self.api.post(
            '/api/django/rh/plans-succession/',
            {'poste_cle': poste_cle.id, 'successeur': etranger.id},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_isolation_societe(self):
        PosteCle.objects.create(
            company=self.co, poste=self.poste, criticite='critique')
        co_b = make_company('nthcm12-d', 'D')
        rh_b = make_user(co_b, 'nthcm12-rh-d')
        self.assertEqual(selectors.couverture_postes_cles(co_b), [])
        resp = auth(rh_b).get('/api/django/rh/postes-cles/couverture/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(list(resp.data), [])
