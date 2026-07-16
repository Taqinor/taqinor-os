"""Tests du tableau de bord admin (NTIDE6).

Couvre : KPI par statut, top 5 par votes, plus récentes, heat-chart par
contexte, accès réservé au palier admin/responsable (pas au rôle limité),
isolation multi-société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.innovation import selectors
from apps.innovation.models import Idee

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


class DashboardSelectorsTests(TestCase):
    def setUp(self):
        self.co_a = make_company('innov-dash-a', 'A')
        self.co_b = make_company('innov-dash-b', 'B')

    def test_par_statut_counts(self):
        Idee.objects.create(company=self.co_a, titre='1', statut=Idee.Statut.OUVERT)
        Idee.objects.create(company=self.co_a, titre='2', statut=Idee.Statut.OUVERT)
        Idee.objects.create(company=self.co_a, titre='3', statut=Idee.Statut.RETENUE)
        Idee.objects.create(company=self.co_b, titre='autre société')
        data = selectors.idees_par_statut(self.co_a)
        self.assertEqual(data['ouvert'], 2)
        self.assertEqual(data['retenue'], 1)
        self.assertEqual(data['total'], 3)

    def test_top_votes_orders_desc(self):
        Idee.objects.create(company=self.co_a, titre='Bas', votes_count=1)
        Idee.objects.create(company=self.co_a, titre='Haut', votes_count=10)
        data = selectors.top_votes(self.co_a)
        self.assertEqual(data[0]['titre'], 'Haut')
        self.assertEqual(data[1]['titre'], 'Bas')

    def test_top_votes_limit(self):
        for i in range(8):
            Idee.objects.create(company=self.co_a, titre=f'idée {i}', votes_count=i)
        data = selectors.top_votes(self.co_a, limit=5)
        self.assertEqual(len(data), 5)

    def test_plus_recentes_orders_desc(self):
        first = Idee.objects.create(company=self.co_a, titre='Première')
        second = Idee.objects.create(company=self.co_a, titre='Seconde')
        data = selectors.plus_recentes(self.co_a)
        self.assertEqual(data[0]['id'], second.id)
        self.assertEqual(data[1]['id'], first.id)

    def test_heat_par_contexte(self):
        Idee.objects.create(company=self.co_a, titre='1', contexte='SAV')
        Idee.objects.create(company=self.co_a, titre='2', contexte='SAV')
        Idee.objects.create(company=self.co_a, titre='3', contexte='Stock')
        Idee.objects.create(company=self.co_a, titre='4', contexte='')
        data = selectors.heat_par_contexte(self.co_a)
        self.assertEqual(data[0], {'contexte': 'SAV', 'nombre': 2})
        self.assertEqual(len(data), 2)  # le contexte vide est ignoré


class DashboardApiTests(TestCase):
    BASE = '/api/django/innovation/idees/tableau-bord/'

    def setUp(self):
        self.co_a = make_company('innov-dashapi-a', 'A')
        self.co_b = make_company('innov-dashapi-b', 'B')
        self.admin_a = make_user(self.co_a, 'innov-dashapi-admin', role='admin')
        self.normal_a = make_user(self.co_a, 'innov-dashapi-normal', role='normal')

    def test_admin_can_view_dashboard(self):
        Idee.objects.create(company=self.co_a, titre='X')
        resp = auth(self.admin_a).get(self.BASE)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('par_statut', resp.data)
        self.assertIn('top_votes', resp.data)
        self.assertIn('plus_recentes', resp.data)
        self.assertIn('heat_contexte', resp.data)

    def test_normal_role_refused(self):
        resp = auth(self.normal_a).get(self.BASE)
        self.assertEqual(resp.status_code, 403)

    def test_dashboard_isolated_per_company(self):
        Idee.objects.create(company=self.co_b, titre='autre société')
        resp = auth(self.admin_a).get(self.BASE)
        self.assertEqual(resp.data['par_statut']['total'], 0)
