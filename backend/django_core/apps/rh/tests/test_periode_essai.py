"""Tests XRH1 — période d'essai (suivi + alerte).

Couvre :
* la famille ``fin_essai`` du sélecteur unifié ``echeances_rh`` (FG175) :
  un employé en essai remonte AVANT ``essai_date_fin`` dans la fenêtre ;
* l'endpoint ``employes/{id}/confirmer-essai`` : la confirmation efface
  ``essai_date_fin`` et retire l'employé de l'échéance ;
* le renouvellement (``essai_renouvele``) ;
* l'isolation multi-société.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh import selectors
from apps.rh.models import DossierEmploye

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, **kwargs):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E', **kwargs)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EcheanceEssaiSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('essai-a', 'A')
        self.today = date(2026, 6, 1)

    def test_essai_remonte_avant_echeance(self):
        emp = make_employe(
            self.co, 'E001', essai_date_fin=self.today + timedelta(days=10))
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        types = {r['type'] for r in rows}
        self.assertIn('fin_essai', types)
        row = next(r for r in rows if r['type'] == 'fin_essai')
        self.assertEqual(row['employe_id'], emp.id)
        self.assertEqual(row['jours_restants'], 10)

    def test_essai_deja_expire_inclus(self):
        make_employe(
            self.co, 'E002', essai_date_fin=self.today - timedelta(days=3))
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        row = next(r for r in rows if r['type'] == 'fin_essai')
        self.assertEqual(row['jours_restants'], -3)

    def test_hors_fenetre_exclu(self):
        make_employe(
            self.co, 'E003', essai_date_fin=self.today + timedelta(days=90))
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        self.assertEqual([r for r in rows if r['type'] == 'fin_essai'], [])

    def test_sans_essai_exclu(self):
        make_employe(self.co, 'E004')
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        self.assertEqual([r for r in rows if r['type'] == 'fin_essai'], [])

    def test_isolation_societe(self):
        co_b = make_company('essai-b', 'B')
        make_employe(
            co_b, 'B001', essai_date_fin=self.today + timedelta(days=5))
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        self.assertEqual([r for r in rows if r['type'] == 'fin_essai'], [])


class ConfirmerEssaiApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('essai-api-a', 'A')
        self.co_b = make_company('essai-api-b', 'B')
        self.user_a = make_user(self.co_a, 'essai-a')
        self.user_b = make_user(self.co_b, 'essai-b')

    def test_confirmer_essai_efface_date_fin(self):
        emp = make_employe(
            self.co_a, 'E010',
            essai_date_fin=date(2026, 6, 1) + timedelta(days=5))
        resp = auth(self.user_a).post(
            f'{EMPLOYES}{emp.id}/confirmer-essai/')
        self.assertEqual(resp.status_code, 200, resp.data)
        emp.refresh_from_db()
        self.assertIsNone(emp.essai_date_fin)
        self.assertNotIn('fin_essai', {
            r['type'] for r in selectors.echeances_rh(
                self.co_a, within_days=30,
                today=date(2026, 6, 1))})

    def test_confirmer_essai_sans_essai_en_cours_400(self):
        emp = make_employe(self.co_a, 'E011')
        resp = auth(self.user_a).post(
            f'{EMPLOYES}{emp.id}/confirmer-essai/')
        self.assertEqual(resp.status_code, 400)

    def test_renouvellement_persiste(self):
        emp = make_employe(
            self.co_a, 'E012',
            essai_date_fin=date(2026, 6, 1) + timedelta(days=30))
        resp = auth(self.user_a).patch(
            f'{EMPLOYES}{emp.id}/', {'essai_renouvele': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        emp.refresh_from_db()
        self.assertTrue(emp.essai_renouvele)

    def test_isolation_tenant_cross_company_404(self):
        emp = make_employe(
            self.co_a, 'E013',
            essai_date_fin=date(2026, 6, 1) + timedelta(days=5))
        resp = auth(self.user_b).post(
            f'{EMPLOYES}{emp.id}/confirmer-essai/')
        self.assertEqual(resp.status_code, 404)
