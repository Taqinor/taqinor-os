"""Tests de la baseline de planning — plan vs réel (PROJ13).

Couvre : prise d'un snapshot figeant les dates/charge de toutes les tâches,
comparaison plan vs réel (écarts de début/fin en jours, dérive de charge,
glissement maximal), survie d'une ligne quand la tâche est supprimée, société
posée côté serveur, isolation multi-société, endpoints baseline/comparer et
accès Administrateur/Responsable.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import selectors, services
from apps.gestion_projet.models import (
    BaselinePlanning,
    BaselineTache,
    Projet,
    Tache,
)

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
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class BaselineServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-base', 'S')
        self.user = make_user(self.co, 'base-u')
        self.p = Projet.objects.create(company=self.co, code='P', nom='P')
        self.t = Tache.objects.create(
            company=self.co, projet=self.p, libelle='A', code_wbs='1',
            date_debut_prevue=date(2026, 1, 1),
            date_fin_prevue=date(2026, 1, 5),
            charge_estimee=Decimal('4'))

    def test_snapshot_freezes_tasks(self):
        baseline = services.creer_baseline(
            self.p, libelle='Initiale', auteur=self.user)
        self.assertEqual(baseline.company, self.co)
        self.assertEqual(baseline.auteur, self.user)
        ligne = BaselineTache.objects.get(baseline=baseline)
        self.assertEqual(ligne.tache, self.t)
        self.assertEqual(ligne.date_debut_prevue, date(2026, 1, 1))
        self.assertEqual(ligne.tache_libelle, 'A')
        self.assertEqual(ligne.company, self.co)

    def test_compare_detects_slippage(self):
        baseline = services.creer_baseline(self.p, auteur=self.user)
        # Slip the task: +3 days on both ends, charge +1.
        self.t.date_debut_prevue = date(2026, 1, 4)
        self.t.date_fin_prevue = date(2026, 1, 8)
        self.t.charge_estimee = Decimal('5')
        self.t.save()
        result = selectors.comparer_baseline(baseline)
        ligne = result['lignes'][0]
        self.assertEqual(ligne['ecart_debut_jours'], 3)
        self.assertEqual(ligne['ecart_fin_jours'], 3)
        self.assertEqual(ligne['derive_charge'], '1.00')
        self.assertEqual(result['glissement_max_fin'], 3)

    def test_compare_no_change(self):
        baseline = services.creer_baseline(self.p, auteur=self.user)
        result = selectors.comparer_baseline(baseline)
        ligne = result['lignes'][0]
        self.assertEqual(ligne['ecart_debut_jours'], 0)
        self.assertEqual(ligne['ecart_fin_jours'], 0)
        self.assertEqual(result['glissement_max_fin'], 0)

    def test_line_survives_task_deletion(self):
        baseline = services.creer_baseline(self.p, auteur=self.user)
        self.t.delete()
        result = selectors.comparer_baseline(baseline)
        ligne = result['lignes'][0]
        self.assertTrue(ligne['tache_supprimee'])
        self.assertIsNone(ligne['tache'])
        self.assertEqual(ligne['libelle'], 'A')   # frozen label survives
        self.assertIsNone(ligne['ecart_fin_jours'])


class BaselineEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('gp-base-a', 'A')
        self.co_b = make_company('gp-base-b', 'B')
        self.user_a = make_user(self.co_a, 'base-a')
        self.p = Projet.objects.create(company=self.co_a, code='P', nom='P')
        self.t = Tache.objects.create(
            company=self.co_a, projet=self.p, libelle='A',
            date_debut_prevue=date(2026, 1, 1),
            date_fin_prevue=date(2026, 1, 5))
        self.proj_url = (
            f'/api/django/gestion-projet/projets/{self.p.id}/baseline/')

    def test_snapshot_endpoint_forces_company_and_author(self):
        resp = auth(self.user_a).post(
            self.proj_url, {'libelle': 'V1'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        baseline = BaselinePlanning.objects.get(id=resp.data['id'])
        self.assertEqual(baseline.company, self.co_a)
        self.assertEqual(baseline.auteur, self.user_a)
        self.assertEqual(baseline.lignes.count(), 1)

    def test_compare_endpoint(self):
        resp = auth(self.user_a).post(self.proj_url, {}, format='json')
        bid = resp.data['id']
        self.t.date_fin_prevue = date(2026, 1, 9)
        self.t.save()
        url = f'/api/django/gestion-projet/baselines/{bid}/comparer/'
        resp2 = auth(self.user_a).get(url)
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['glissement_max_fin'], 4)

    def test_isolation(self):
        services.creer_baseline(self.p, auteur=self.user_a)
        user_b = make_user(self.co_b, 'base-b')
        resp = auth(user_b).get('/api/django/gestion-projet/baselines/')
        self.assertEqual(len(rows(resp)), 0)

    def test_compare_cross_company_404(self):
        baseline = services.creer_baseline(self.p, auteur=self.user_a)
        user_b = make_user(self.co_b, 'base-b2')
        url = f'/api/django/gestion-projet/baselines/{baseline.id}/comparer/'
        resp = auth(user_b).get(url)
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_403(self):
        normal = make_user(self.co_a, 'base-normal', role='normal')
        resp = auth(normal).post(self.proj_url, {}, format='json')
        self.assertEqual(resp.status_code, 403)
