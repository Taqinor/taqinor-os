"""Tests ZRH14 — badges de reconnaissance interne (gamification).

Couvre : attribution à un collègue, auto-attribution refusée (400), comptage
par employé, CRUD badges company-scopé, isolation tenant.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import BadgeReconnaissance, DossierEmploye

User = get_user_model()

URL_BADGES = '/api/django/rh/badges-reconnaissance/'
URL_ATTRIB = '/api/django/rh/attributions-badge/'


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


class BadgesReconnaissanceTests(TestCase):
    def setUp(self):
        self.co_a = make_company('bd-a', 'A')
        self.co_b = make_company('bd-b', 'B')
        self.user_a = make_user(self.co_a, 'bd-user-a')
        self.user_b = make_user(self.co_b, 'bd-user-b')
        self.badge = BadgeReconnaissance.objects.create(
            company=self.co_a, nom='Esprit d\'équipe')
        self.dossier_a = DossierEmploye.objects.create(
            company=self.co_a, matricule='BDA', nom='A', prenom='User',
            user=self.user_a)
        self.collegue = DossierEmploye.objects.create(
            company=self.co_a, matricule='BDC', nom='Collegue', prenom='X')

    def test_attribuer_badge_a_collegue(self):
        resp = auth(self.user_a).post(URL_ATTRIB, {
            'badge': self.badge.id, 'beneficiaire': self.collegue.id,
            'message': 'Bravo !',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['beneficiaire'], self.collegue.id)

    def test_auto_attribution_refusee(self):
        resp = auth(self.user_a).post(URL_ATTRIB, {
            'badge': self.badge.id, 'beneficiaire': self.dossier_a.id,
        })
        self.assertEqual(resp.status_code, 400)

    def test_comptage_par_employe(self):
        auth(self.user_a).post(URL_ATTRIB, {
            'badge': self.badge.id, 'beneficiaire': self.collegue.id,
        })
        resp = auth(self.user_a).get(
            URL_BADGES + f'{self.badge.id}/')
        self.assertEqual(resp.data['nombre_attributions'], 1)

    def test_crud_badges_company_scope(self):
        resp = auth(self.user_a).get(URL_BADGES)
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        noms = [b['nom'] for b in rows]
        self.assertIn("Esprit d'équipe", noms)

    def test_isolation_tenant(self):
        resp = auth(self.user_b).get(URL_BADGES)
        rows = resp.data['results'] if isinstance(resp.data, dict) \
            else resp.data
        self.assertEqual(len(rows), 0)

    def test_attribue_par_pose_cote_serveur(self):
        resp = auth(self.user_a).post(URL_ATTRIB, {
            'badge': self.badge.id, 'beneficiaire': self.collegue.id,
            'attribue_par': 99999,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['attribue_par'], self.user_a.id)
