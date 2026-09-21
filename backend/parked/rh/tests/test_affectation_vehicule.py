"""Tests FG198 — Affectation conducteur ↔ véhicule (garde permis).

Couvre :
* Garde permis : affectation REFUSÉE (400) sans permis valide, ACCEPTÉE avec
  permis valide (permis_verifie posé côté serveur).
* ``company`` posée CÔTÉ SERVEUR ; FK employe d'une autre société refusé.
* Action ``terminer`` (idempotente, pose date_fin, 404 autre tenant).
* Filtres + isolation + permission (rôle normal 403).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import (
    AffectationVehicule,
    DossierEmploye,
    PermisConduire,
)

User = get_user_model()

URL = '/api/django/rh/affectations-vehicule/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='N', prenom='P')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class AffectationVehiculeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('avh-a', 'A')
        self.co_b = make_company('avh-b', 'B')
        self.user_a = make_user(self.co_a, 'avh-user-a')
        self.user_b = make_user(self.co_b, 'avh-user-b')
        self.emp_a = make_employe(self.co_a, 'AVH1')
        self.emp_b = make_employe(self.co_b, 'AVH2')
        self.today = timezone.localdate()

    def _donner_permis_valide(self, employe):
        PermisConduire.objects.create(
            company=employe.company, employe=employe, categorie='B',
            date_expiration=self.today + timedelta(days=365))

    def test_sans_permis_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id, 'vehicule_id': 7,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(AffectationVehicule.objects.count(), 0)

    def test_permis_expire_refuse(self):
        PermisConduire.objects.create(
            company=self.co_a, employe=self.emp_a, categorie='B',
            date_expiration=self.today - timedelta(days=1))
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id, 'vehicule_id': 7,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_avec_permis_valide_accepte(self):
        self._donner_permis_valide(self.emp_a)
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id, 'vehicule_id': 7,
            'date_debut': self.today.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        av = AffectationVehicule.objects.get(id=resp.data['id'])
        self.assertEqual(av.company, self.co_a)
        self.assertTrue(av.permis_verifie)

    def test_employe_autre_societe_refuse(self):
        self._donner_permis_valide(self.emp_b)
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_b.id, 'vehicule_id': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_terminer_idempotent_et_404(self):
        self._donner_permis_valide(self.emp_a)
        av = AffectationVehicule.objects.create(
            company=self.co_a, employe=self.emp_a, vehicule_id=7,
            permis_verifie=True)
        api = auth(self.user_a)
        r1 = api.post(f'{URL}{av.id}/terminer/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['statut'], AffectationVehicule.Statut.TERMINEE)
        self.assertIsNotNone(r1.data['date_fin'])
        r2 = api.post(f'{URL}{av.id}/terminer/')
        self.assertEqual(r2.status_code, 200)
        r3 = auth(self.user_b).post(f'{URL}{av.id}/terminer/')
        self.assertEqual(r3.status_code, 404)

    def test_filtres_et_isolation(self):
        self._donner_permis_valide(self.emp_a)
        AffectationVehicule.objects.create(
            company=self.co_a, employe=self.emp_a, vehicule_id=7,
            statut=AffectationVehicule.Statut.ACTIVE, permis_verifie=True)
        api = auth(self.user_a)
        self.assertEqual(len(rows(api.get(f'{URL}?statut=active'))), 1)
        self.assertEqual(len(rows(api.get(f'{URL}?vehicule_id=7'))), 1)
        self.assertEqual(
            len(rows(api.get(f'{URL}?employe={self.emp_a.id}'))), 1)
        self.assertEqual(len(rows(auth(self.user_b).get(URL))), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'avh-normal', role='normal')
        self.assertEqual(auth(normal).get(URL).status_code, 403)
