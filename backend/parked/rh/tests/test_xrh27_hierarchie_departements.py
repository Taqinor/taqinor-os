"""Tests XRH27 — Hiérarchie de départements.

Couvre :
* un cycle A→B→A est rejeté 400 (API) et à ``clean()`` (modèle) ;
* l'arbre agrège les effectifs enfants (cumulé = propre + descendants) ;
* le filtre cockpit ``?departement=`` est descendant-inclusif ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import Departement, DossierEmploye

User = get_user_model()

DEPARTEMENTS_URL = '/api/django/rh/departements/'
ARBRE_URL = '/api/django/rh/departements/arbre/'
COCKPIT_URL = '/api/django/rh/cockpit/'


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


class HierarchieDepartementsTests(TestCase):
    def setUp(self):
        self.co = make_company('dep-a', 'A')
        self.rh = make_user(self.co, 'dep-rh')
        self.direction = Departement.objects.create(
            company=self.co, nom='Direction')
        self.pole_technique = Departement.objects.create(
            company=self.co, nom='Pôle technique', parent=self.direction)
        self.equipe_pose = Departement.objects.create(
            company=self.co, nom='Équipe pose', parent=self.pole_technique)

    def test_cycle_direct_rejete_modele(self):
        self.direction.parent = self.direction
        with self.assertRaises(ValidationError):
            self.direction.clean()

    def test_cycle_indirect_a_b_a_rejete_modele(self):
        # direction -> pole_technique -> equipe_pose (déjà construit).
        # On tente maintenant direction.parent = equipe_pose (A -> ... -> A).
        self.direction.parent = self.equipe_pose
        with self.assertRaises(ValidationError):
            self.direction.clean()

    def test_cycle_rejete_api_400(self):
        resp = auth(self.rh).patch(
            f'{DEPARTEMENTS_URL}{self.direction.id}/', {
                'parent': self.equipe_pose.id,
            }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_arbre_agrege_effectifs_cumules(self):
        DossierEmploye.objects.create(
            company=self.co, matricule='D1', nom='N', prenom='P',
            departement=self.direction,
            statut=DossierEmploye.Statut.ACTIF)
        DossierEmploye.objects.create(
            company=self.co, matricule='D2', nom='N2', prenom='P2',
            departement=self.pole_technique,
            statut=DossierEmploye.Statut.ACTIF)
        DossierEmploye.objects.create(
            company=self.co, matricule='D3', nom='N3', prenom='P3',
            departement=self.equipe_pose,
            statut=DossierEmploye.Statut.ACTIF)

        arbre = selectors.arbre_departements(self.co)
        self.assertEqual(len(arbre), 1)
        racine = arbre[0]
        self.assertEqual(racine['id'], self.direction.id)
        self.assertEqual(racine['effectif_propre'], 1)
        self.assertEqual(racine['effectif_cumule'], 3)

        pole = racine['enfants'][0]
        self.assertEqual(pole['id'], self.pole_technique.id)
        self.assertEqual(pole['effectif_propre'], 1)
        self.assertEqual(pole['effectif_cumule'], 2)

        equipe = pole['enfants'][0]
        self.assertEqual(equipe['effectif_propre'], 1)
        self.assertEqual(equipe['effectif_cumule'], 1)

    def test_arbre_endpoint(self):
        resp = auth(self.rh).get(ARBRE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['nom'], 'Direction')

    def test_cockpit_filtre_departement_descendant_inclusif(self):
        DossierEmploye.objects.create(
            company=self.co, matricule='D1', nom='N', prenom='P',
            departement=self.direction,
            statut=DossierEmploye.Statut.ACTIF)
        DossierEmploye.objects.create(
            company=self.co, matricule='D2', nom='N2', prenom='P2',
            departement=self.equipe_pose,
            statut=DossierEmploye.Statut.ACTIF)
        autre_dep = Departement.objects.create(company=self.co, nom='Autre')
        DossierEmploye.objects.create(
            company=self.co, matricule='D3', nom='N3', prenom='P3',
            departement=autre_dep,
            statut=DossierEmploye.Statut.ACTIF)

        resp = auth(self.rh).get(
            COCKPIT_URL, {'departement': self.pole_technique.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        # pole_technique + equipe_pose (descendant) = 1 employé (D2) — D1 est
        # sur "direction" (l'ANCÊTRE, pas un descendant) donc exclu.
        self.assertEqual(resp.data['effectif_total'], 1)

    def test_isolation_societe(self):
        co_b = make_company('dep-b', 'B')
        rh_b = make_user(co_b, 'dep-rh-b')
        resp = auth(rh_b).get(ARBRE_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, [])

    def test_parent_autre_societe_rejete(self):
        co_b = make_company('dep-c', 'B')
        dep_b = Departement.objects.create(company=co_b, nom='Dep B')
        resp = auth(self.rh).post(DEPARTEMENTS_URL, {
            'nom': 'Nouveau', 'parent': dep_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
