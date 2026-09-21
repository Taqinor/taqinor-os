"""Tests ZRH11 — rapport de rétention/turnover ANNUEL détaillé.

Couvre : effectif début/fin, entrées/sorties par mois, taux de turnover,
ancienneté moyenne, rétention 12 mois, isolation tenant, distinct du cockpit.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye

User = get_user_model()

URL = '/api/django/rh/employes/rapport-turnover/'


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


class RapportTurnoverTests(TestCase):
    def setUp(self):
        self.co_a = make_company('rt-a', 'A')
        self.co_b = make_company('rt-b', 'B')
        self.user_a = make_user(self.co_a, 'rt-user-a')
        self.user_b = make_user(self.co_b, 'rt-user-b')
        self.today = timezone.localdate()
        self.annee = self.today.year

    def _emp(self, matricule, **extra):
        return DossierEmploye.objects.create(
            company=self.co_a, matricule=matricule, nom='N', prenom='P',
            **extra)

    def test_entrees_sorties_par_mois(self):
        self._emp(
            'E1',
            date_embauche=date(self.annee, 2, 10),
            statut=DossierEmploye.Statut.ACTIF)
        self._emp(
            'E2',
            date_embauche=date(self.annee - 5, 1, 1),
            date_sortie=date(self.annee, 3, 15),
            statut=DossierEmploye.Statut.SORTI)
        resp = auth(self.user_a).get(URL, {'annee': self.annee})
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(data['annee'], self.annee)
        par_mois = {e['mois']: e for e in data['par_mois']}
        self.assertEqual(par_mois[2]['entrees'], 1)
        self.assertEqual(par_mois[3]['sorties'], 1)
        self.assertEqual(data['entrees_total'], 1)
        self.assertEqual(data['sorties_total'], 1)

    def test_taux_turnover_et_effectifs(self):
        # Deux présents toute l'année.
        self._emp(
            'E1', date_embauche=date(self.annee - 3, 1, 1),
            statut=DossierEmploye.Statut.ACTIF)
        self._emp(
            'E2', date_embauche=date(self.annee - 2, 1, 1),
            statut=DossierEmploye.Statut.ACTIF)
        resp = auth(self.user_a).get(URL, {'annee': self.annee})
        data = resp.data
        self.assertEqual(data['effectif_debut'], 2)
        self.assertEqual(data['effectif_fin'], 2)
        self.assertEqual(data['taux_turnover_pct'], 0.0)
        self.assertGreater(data['anciennete_moyenne_ans'], 0)

    def test_division_par_zero_gardee(self):
        # Aucun employé -> pas de crash, taux 0.
        resp = auth(self.user_a).get(URL, {'annee': self.annee})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['taux_turnover_pct'], 0.0)

    def test_retention_12m(self):
        annee_precedente = self.annee - 1
        # Embauché il y a >12 mois, encore présent -> compte comme jugeable
        # et retenu.
        self._emp(
            'E1', date_embauche=date(annee_precedente, 1, 1),
            statut=DossierEmploye.Statut.ACTIF)
        # Embauché il y a >12 mois, sorti avant les 12 mois -> jugeable, non
        # retenu.
        self._emp(
            'E2', date_embauche=date(annee_precedente, 1, 1),
            date_sortie=date(annee_precedente, 6, 1),
            statut=DossierEmploye.Statut.SORTI)
        resp = auth(self.user_a).get(URL, {'annee': self.annee})
        data = resp.data
        self.assertIsNotNone(data['retention_12m_pct'])
        self.assertEqual(data['retention_12m_pct'], 50.0)

    def test_isolation_tenant(self):
        self._emp('E1', date_embauche=date(self.annee, 1, 5))
        resp = auth(self.user_b).get(URL, {'annee': self.annee})
        self.assertEqual(resp.data['effectif_debut'], 0)
        self.assertEqual(resp.data['entrees_total'], 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'rt-normal', role='normal')
        resp = auth(normal).get(URL, {'annee': self.annee})
        self.assertEqual(resp.status_code, 403)
