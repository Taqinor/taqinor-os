"""Tests FG197 — Permis de conduire & habilitation à conduire.

Couvre :
* Création : ``company`` posée CÔTÉ SERVEUR ; FK employe d'une autre société
  refusé ; (employe, categorie) unique ; champ ``valide`` calculé.
* Sélecteur ``peut_conduire`` (permis valide / expiré / catégorie, scopé
  société).
* Action ``expirant-bientot`` (exclut sans-échéance et déjà-expirés).
* Filtres + isolation + permission (rôle normal 403).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, PermisConduire

User = get_user_model()

URL = '/api/django/rh/permis-conduire/'


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


class PermisConduireTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pc-a', 'A')
        self.co_b = make_company('pc-b', 'B')
        self.user_a = make_user(self.co_a, 'pc-user-a')
        self.user_b = make_user(self.co_b, 'pc-user-b')
        self.emp_a = make_employe(self.co_a, 'PC1')
        self.emp_b = make_employe(self.co_b, 'PC2')
        self.today = timezone.localdate()

    def test_create_company_cote_serveur_et_valide(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id, 'categorie': 'B',
            'numero': 'AB12345',
            'date_expiration': (self.today + timedelta(days=365)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        pc = PermisConduire.objects.get(id=resp.data['id'])
        self.assertEqual(pc.company, self.co_a)
        self.assertTrue(resp.data['valide'])

    def test_permis_expire_non_valide(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id, 'categorie': 'C',
            'date_expiration': (self.today - timedelta(days=1)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data['valide'])

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_b.id, 'categorie': 'B',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_unicite_employe_categorie(self):
        PermisConduire.objects.create(
            company=self.co_a, employe=self.emp_a, categorie='B')
        with self.assertRaises(IntegrityError):
            PermisConduire.objects.create(
                company=self.co_a, employe=self.emp_a, categorie='B')

    def test_selecteur_peut_conduire(self):
        # Permis valide.
        PermisConduire.objects.create(
            company=self.co_a, employe=self.emp_a, categorie='B',
            date_expiration=self.today + timedelta(days=10))
        self.assertTrue(selectors.peut_conduire(self.co_a, self.emp_a.id))
        self.assertTrue(
            selectors.peut_conduire(self.co_a, self.emp_a.id, categorie='B'))
        self.assertFalse(
            selectors.peut_conduire(self.co_a, self.emp_a.id, categorie='C'))
        # Autre société : non.
        self.assertFalse(selectors.peut_conduire(self.co_b, self.emp_a.id))

    def test_selecteur_peut_conduire_expire(self):
        PermisConduire.objects.create(
            company=self.co_a, employe=self.emp_a, categorie='B',
            date_expiration=self.today - timedelta(days=1))
        self.assertFalse(selectors.peut_conduire(self.co_a, self.emp_a.id))

    def test_selecteur_peut_conduire_sans_echeance(self):
        PermisConduire.objects.create(
            company=self.co_a, employe=self.emp_a, categorie='B',
            date_expiration=None)
        self.assertTrue(selectors.peut_conduire(self.co_a, self.emp_a.id))

    def test_expirant_bientot(self):
        PermisConduire.objects.create(
            company=self.co_a, employe=self.emp_a, categorie='B',
            date_expiration=self.today + timedelta(days=10))
        # Sans échéance et déjà-expiré ne sortent pas.
        emp2 = make_employe(self.co_a, 'PC3')
        PermisConduire.objects.create(
            company=self.co_a, employe=emp2, categorie='B',
            date_expiration=None)
        emp3 = make_employe(self.co_a, 'PC4')
        PermisConduire.objects.create(
            company=self.co_a, employe=emp3, categorie='B',
            date_expiration=self.today - timedelta(days=5))
        resp = auth(self.user_a).get(f'{URL}expirant-bientot/?within=30')
        self.assertEqual(len(rows(resp)), 1)

    def test_isolation_et_permission(self):
        PermisConduire.objects.create(
            company=self.co_a, employe=self.emp_a, categorie='B')
        self.assertEqual(len(rows(auth(self.user_b).get(URL))), 0)
        normal = make_user(self.co_a, 'pc-normal', role='normal')
        self.assertEqual(auth(normal).get(URL).status_code, 403)
