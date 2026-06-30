"""Tests QHSE34 — Statistiques TF / TG (taux de fréquence / gravité).

Couvre :
* le sélecteur ``statistiques_tf_tg`` : formules TF/TG, compte des accidents
  AVEC ARRÊT depuis le registre QHSE (``Incident`` de type ``accident``),
  bornage de période, garde-fou heures ≤ 0 → TF/TG ``None`` ;
* l'action API ``GET …/incidents/statistiques-tf-tg/`` (``?heures=`` /
  ``?jours_perdus=`` / dates), scopée société + rôle.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import Incident
from apps.qhse.selectors import statistiques_tf_tg

User = get_user_model()

STATS_URL = '/api/django/qhse/incidents/statistiques-tf-tg/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_accident(company, jour, reference, type_incident='accident'):
    return Incident.objects.create(
        company=company, titre='Chute', type_incident=type_incident,
        reference=reference, date_incident=jour)


class StatistiquesTfTgSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('co-tftg', 'CoTfTg')

    def test_tf_tg_formules(self):
        # 2 accidents, 200 000 h travaillées, 10 jours perdus.
        make_accident(self.company, date(2026, 6, 1), 'INC-1')
        make_accident(self.company, date(2026, 6, 2), 'INC-2')
        stats = statistiques_tf_tg(
            self.company, heures_travaillees=200000, jours_perdus=10)
        self.assertEqual(stats['accidents_avec_arret'], 2)
        # TF = 2 * 1_000_000 / 200_000 = 10.00
        self.assertEqual(stats['tf'], Decimal('10.00'))
        # TG = 10 * 1_000 / 200_000 = 0.05
        self.assertEqual(stats['tg'], Decimal('0.05'))

    def test_seuls_accidents_comptes(self):
        make_accident(self.company, date(2026, 6, 1), 'INC-1',
                      type_incident='accident')
        make_accident(self.company, date(2026, 6, 2), 'INC-2',
                      type_incident='presqu_accident')
        make_accident(self.company, date(2026, 6, 3), 'INC-3',
                      type_incident='incident')
        stats = statistiques_tf_tg(self.company, heures_travaillees=100000)
        self.assertEqual(stats['accidents_avec_arret'], 1)

    def test_bornage_periode(self):
        make_accident(self.company, date(2026, 5, 1), 'INC-1')
        make_accident(self.company, date(2026, 6, 15), 'INC-2')
        stats = statistiques_tf_tg(
            self.company, heures_travaillees=100000,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30))
        self.assertEqual(stats['accidents_avec_arret'], 1)

    def test_heures_zero_tf_tg_none(self):
        make_accident(self.company, date(2026, 6, 1), 'INC-1')
        stats = statistiques_tf_tg(self.company, heures_travaillees=0)
        self.assertIsNone(stats['tf'])
        self.assertIsNone(stats['tg'])

    def test_scope_societe(self):
        other = make_company('co-tftg-2', 'CoTfTg2')
        make_accident(self.company, date(2026, 6, 1), 'INC-1')
        make_accident(other, date(2026, 6, 2), 'INC-1')
        stats = statistiques_tf_tg(self.company, heures_travaillees=100000)
        self.assertEqual(stats['accidents_avec_arret'], 1)


class StatistiquesTfTgApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-tftg-api', 'CoTfTgApi')
        self.user = make_user(self.company, 'tftg-resp')
        self.client_api = auth_client(self.user)

    def test_api_heures_parametre(self):
        make_accident(self.company, date(2026, 6, 1), 'INC-1')
        resp = self.client_api.get(
            STATS_URL, {'heures': '500000', 'jours_perdus': '5'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['accidents_avec_arret'], 1)
        # TF = 1 * 1_000_000 / 500_000 = 2.00
        self.assertEqual(resp.data['tf'], '2.00')
        # TG = 5 * 1_000 / 500_000 = 0.01
        self.assertEqual(resp.data['tg'], '0.01')

    def test_api_sans_heures_tf_none(self):
        make_accident(self.company, date(2026, 6, 1), 'INC-1')
        resp = self.client_api.get(STATS_URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['tf'])

    def test_role_normal_refuse(self):
        normal = make_user(self.company, 'tftg-normal', role='normal')
        resp = auth_client(normal).get(STATS_URL)
        self.assertEqual(resp.status_code, 403)
