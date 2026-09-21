"""Tests ZRH17 — recherche transverse d'employés par compétence et niveau.

Couvre : filtre niveau_min, intersection multi-compétences, champs non
sensibles (serializer annuaire), isolation tenant, accès à tout employé
authentifié (pas seulement responsable/admin).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Competence, CompetenceEmploye, DossierEmploye

User = get_user_model()


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


class EmployesParCompetenceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('epc-a', 'A')
        self.co_b = make_company('epc-b', 'B')
        self.user_a = make_user(self.co_a, 'epc-user-a')
        self.user_b = make_user(self.co_b, 'epc-user-b')
        self.comp1 = Competence.objects.create(
            company=self.co_a, code='C1', libelle='Raccordement DC')
        self.comp2 = Competence.objects.create(
            company=self.co_a, code='C2', libelle='Soudure')
        self.e1 = DossierEmploye.objects.create(
            company=self.co_a, matricule='E1', nom='N1', prenom='P1')
        self.e2 = DossierEmploye.objects.create(
            company=self.co_a, matricule='E2', nom='N2', prenom='P2')
        self.e3 = DossierEmploye.objects.create(
            company=self.co_a, matricule='E3', nom='N3', prenom='P3')
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.e1, competence=self.comp1,
            niveau=4)
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.e2, competence=self.comp1,
            niveau=1)
        CompetenceEmploye.objects.create(
            company=self.co_a, employe=self.e1, competence=self.comp2,
            niveau=3)

    def _url(self, competence):
        return f'/api/django/rh/competences/{competence.id}/employes/'

    def test_filtre_niveau_min(self):
        resp = auth(self.user_a).get(
            self._url(self.comp1), {'niveau_min': 3})
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [e['id'] for e in resp.data]
        self.assertIn(self.e1.id, ids)
        self.assertNotIn(self.e2.id, ids)
        self.assertNotIn(self.e3.id, ids)

    def test_tri_niveau_decroissant(self):
        resp = auth(self.user_a).get(self._url(self.comp1))
        ids = [e['id'] for e in resp.data]
        self.assertEqual(ids[0], self.e1.id)

    def test_intersection_multi_competences(self):
        resp = auth(self.user_a).get(
            self._url(self.comp1),
            {'niveau_min': 1, 'competences': str(self.comp2.id)})
        ids = [e['id'] for e in resp.data]
        # Seul e1 a niveau>=1 sur comp1 ET comp2.
        self.assertEqual(ids, [self.e1.id])

    def test_champs_non_sensibles(self):
        resp = auth(self.user_a).get(self._url(self.comp1))
        for entry in resp.data:
            self.assertNotIn('salaire', entry)
            self.assertNotIn('cin', entry)
            self.assertNotIn('rib', entry)

    def test_isolation_tenant(self):
        resp = auth(self.user_b).get(self._url(self.comp1))
        self.assertEqual(resp.status_code, 404)

    def test_accessible_employe_normal(self):
        # ZRH17 : accessible à tout employé authentifié, pas seulement
        # responsable/admin.
        resp = auth(self.user_a).get(self._url(self.comp1))
        self.assertEqual(resp.status_code, 200)
