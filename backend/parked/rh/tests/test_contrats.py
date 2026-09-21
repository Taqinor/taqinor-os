"""Tests FG155 — typage du contrat, dates de contrat et alerte fin de CDD.

Couvre : les choix de ``type_contrat`` acceptés à la création, la persistance
des dates de contrat, et l'action ``cdd-a-echeance`` qui ne renvoie QUE les CDD
de la société de l'appelant dont la fin tombe dans la fenêtre — en excluant les
CDI, les CDD hors fenêtre / sans date / expirés, et les CDD d'une autre société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh.models import DossierEmploye

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class ContratTypeDatesTests(TestCase):
    BASE = '/api/django/rh/employes/'

    def setUp(self):
        self.co_a = make_company('rh-c-a', 'A')
        self.user_a = make_user(self.co_a, 'rh-c-a')

    def test_create_accepts_cdd_type_and_dates(self):
        api = auth(self.user_a)
        today = timezone.localdate()
        fin = today + timedelta(days=20)
        payload = {
            'matricule': 'CDD001', 'nom': 'Alami', 'prenom': 'Youssef',
            'type_contrat': 'cdd',
            'contrat_date_debut': today.isoformat(),
            'contrat_date_fin': fin.isoformat(),
        }
        resp = api.post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = DossierEmploye.objects.get(id=resp.data['id'])
        self.assertEqual(obj.type_contrat, DossierEmploye.TypeContrat.CDD)
        self.assertEqual(obj.contrat_date_debut, today)
        self.assertEqual(obj.contrat_date_fin, fin)

    def test_each_contract_type_choice_accepted(self):
        api = auth(self.user_a)
        for i, choix in enumerate(DossierEmploye.TypeContrat.values):
            payload = {
                'matricule': f'EMP{i:03d}', 'nom': 'X', 'prenom': 'Y',
                'type_contrat': choix,
            }
            resp = api.post(self.BASE, payload, format='json')
            self.assertEqual(resp.status_code, 201, resp.data)
            self.assertEqual(resp.data['type_contrat'], choix)

    def test_invalid_contract_type_rejected(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'matricule': 'BAD001', 'nom': 'X', 'prenom': 'Y',
            'type_contrat': 'freelance',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class CddAEcheanceTests(TestCase):
    URL = '/api/django/rh/employes/cdd-a-echeance/'

    def setUp(self):
        self.co_a = make_company('rh-e-a', 'A')
        self.co_b = make_company('rh-e-b', 'B')
        self.user_a = make_user(self.co_a, 'rh-e-a')
        self.user_b = make_user(self.co_b, 'rh-e-b')
        self.today = timezone.localdate()

    def _emp(self, company, matricule, **extra):
        base = dict(company=company, matricule=matricule, nom='N', prenom='P')
        base.update(extra)
        return DossierEmploye.objects.create(**base)

    def test_returns_only_in_window_same_company_cdd(self):
        # Doit apparaître : CDD société A finissant dans 10 jours (fenêtre 30).
        ok = self._emp(
            self.co_a, 'OK', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=self.today + timedelta(days=10))
        # Exclus : CDI (même date), CDD hors fenêtre, CDD sans date,
        # CDD déjà expiré, et CDD d'une AUTRE société.
        self._emp(
            self.co_a, 'CDI', type_contrat=DossierEmploye.TypeContrat.CDI,
            contrat_date_fin=self.today + timedelta(days=10))
        self._emp(
            self.co_a, 'FAR', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=self.today + timedelta(days=120))
        self._emp(
            self.co_a, 'NODATE', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=None)
        self._emp(
            self.co_a, 'PAST', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=self.today - timedelta(days=5))
        self._emp(
            self.co_b, 'OTHERCO', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=self.today + timedelta(days=10))

        resp = auth(self.user_a).get(self.URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [ok.id])

    def test_within_param_widens_window(self):
        soon = self._emp(
            self.co_a, 'SOON', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=self.today + timedelta(days=10))
        later = self._emp(
            self.co_a, 'LATER', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=self.today + timedelta(days=50))

        # Fenêtre par défaut (30 j) : seul SOON.
        resp = auth(self.user_a).get(self.URL)
        self.assertEqual([r['id'] for r in rows(resp)], [soon.id])

        # within=60 : SOON puis LATER (triés par fin de contrat).
        resp = auth(self.user_a).get(self.URL, {'within': 60})
        self.assertEqual([r['id'] for r in rows(resp)], [soon.id, later.id])

    def test_isolation_other_company_sees_nothing(self):
        self._emp(
            self.co_a, 'A-CDD', type_contrat=DossierEmploye.TypeContrat.CDD,
            contrat_date_fin=self.today + timedelta(days=10))
        resp = auth(self.user_b).get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refused(self):
        normal = make_user(self.co_a, 'rh-e-normal', role='normal')
        resp = auth(normal).get(self.URL)
        self.assertEqual(resp.status_code, 403)
