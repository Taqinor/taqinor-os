"""Tests FG192 — Éléments variables de paie (export prestataire paie).

Couvre :
* Création : ``company`` posée CÔTÉ SERVEUR, CRUD ; validation mois 1-12.
* FK ``employe`` d'une autre société refusé.
* Unicité (employe, annee, mois).
* Action ``marquer-exporte`` (idempotente, pose date_export, 404 autre tenant).
* Export CSV (``export-paie-csv``) — en-tête + lignes, scopé société.
* Filtres ``?employe=`` / ``?annee=`` / ``?mois=`` / ``?statut=``.
* Isolation + permission (rôle normal 403).
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, ElementsVariablesPaie

User = get_user_model()

URL = '/api/django/rh/elements-variables-paie/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, nom='Nom', prenom='Prenom'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class ElementsVariablesPaieTests(TestCase):
    def setUp(self):
        self.co_a = make_company('evp-a', 'A')
        self.co_b = make_company('evp-b', 'B')
        self.user_a = make_user(self.co_a, 'evp-user-a')
        self.user_b = make_user(self.co_b, 'evp-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_create_company_cote_serveur(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id,
            'annee': 2026, 'mois': 6,
            'heures_normales': '173.00', 'heures_supp': '8.50',
            'primes': '500.00', 'retenues': '200.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        evp = ElementsVariablesPaie.objects.get(id=resp.data['id'])
        self.assertEqual(evp.company, self.co_a)
        self.assertEqual(evp.statut, ElementsVariablesPaie.Statut.BROUILLON)

    def test_mois_invalide_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_a.id, 'annee': 2026, 'mois': 13,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(URL, {
            'employe': self.emp_b.id, 'annee': 2026, 'mois': 6,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_unicite_employe_annee_mois(self):
        ElementsVariablesPaie.objects.create(
            company=self.co_a, employe=self.emp_a, annee=2026, mois=6)
        with self.assertRaises(IntegrityError):
            ElementsVariablesPaie.objects.create(
                company=self.co_a, employe=self.emp_a, annee=2026, mois=6)

    def test_marquer_exporte_idempotent(self):
        evp = ElementsVariablesPaie.objects.create(
            company=self.co_a, employe=self.emp_a, annee=2026, mois=6)
        api = auth(self.user_a)
        r1 = api.post(f'{URL}{evp.id}/marquer-exporte/')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['statut'], ElementsVariablesPaie.Statut.EXPORTE)
        self.assertIsNotNone(r1.data['date_export'])
        r2 = api.post(f'{URL}{evp.id}/marquer-exporte/')
        self.assertEqual(r2.status_code, 200)

    def test_marquer_exporte_autre_tenant_404(self):
        evp = ElementsVariablesPaie.objects.create(
            company=self.co_a, employe=self.emp_a, annee=2026, mois=6)
        resp = auth(self.user_b).post(f'{URL}{evp.id}/marquer-exporte/')
        self.assertEqual(resp.status_code, 404)

    def test_export_csv(self):
        ElementsVariablesPaie.objects.create(
            company=self.co_a, employe=self.emp_a, annee=2026, mois=6,
            heures_normales=173)
        ElementsVariablesPaie.objects.create(
            company=self.co_b, employe=self.emp_b, annee=2026, mois=6)
        resp = auth(self.user_a).get(f'{URL}export-paie-csv/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        body = resp.content.decode('utf-8')
        self.assertIn('Matricule', body)
        self.assertIn('EA1', body)
        self.assertNotIn('EB1', body)

    def test_filtres(self):
        ElementsVariablesPaie.objects.create(
            company=self.co_a, employe=self.emp_a, annee=2026, mois=6,
            statut=ElementsVariablesPaie.Statut.VALIDE)
        emp2 = make_employe(self.co_a, 'EA2')
        ElementsVariablesPaie.objects.create(
            company=self.co_a, employe=emp2, annee=2025, mois=12)
        api = auth(self.user_a)
        self.assertEqual(len(rows(api.get(f'{URL}?annee=2026'))), 1)
        self.assertEqual(len(rows(api.get(f'{URL}?mois=12'))), 1)
        self.assertEqual(len(rows(api.get(f'{URL}?statut=valide'))), 1)
        self.assertEqual(
            len(rows(api.get(f'{URL}?employe={self.emp_a.id}'))), 1)

    def test_isolation(self):
        ElementsVariablesPaie.objects.create(
            company=self.co_a, employe=self.emp_a, annee=2026, mois=6)
        resp = auth(self.user_b).get(URL)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'evp-normal', role='normal')
        resp = auth(normal).get(URL)
        self.assertEqual(resp.status_code, 403)
