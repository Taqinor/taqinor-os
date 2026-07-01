"""Tests API de la Comptabilité générale.

Couvre : société posée côté serveur (jamais du corps), isolation entre sociétés
(A ne voit pas les écritures/comptes de B), équilibre exigé à la création d'une
écriture via l'API, seeding via l'action, et accès réservé au palier
Administrateur/Responsable.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import CompteComptable, EcritureComptable, Journal

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


class ComptaApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('api-a', 'API A')
        self.co_b = make_company('api-b', 'API B')
        self.user_a = make_user(self.co_a, 'compta-a')
        self.user_b = make_user(self.co_b, 'compta-b')
        services.seed_plan_comptable(self.co_a)
        services.seed_journaux(self.co_a)
        services.seed_plan_comptable(self.co_b)
        services.seed_journaux(self.co_b)

    def test_seed_action_idempotent(self):
        co = make_company('api-seed', 'API Seed')
        user = make_user(co, 'compta-seed')
        api = auth(user)
        resp = api.post('/api/django/compta/plans/seed/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            CompteComptable.objects.filter(company=co, numero='3421').exists())
        # COMPTA4 — 6 journaux standards (VTE/ACH/BNK/CSH/OD/AN).
        self.assertEqual(Journal.objects.filter(company=co).count(), 6)

    def test_comptes_isolation(self):
        api = auth(self.user_a)
        resp = api.get('/api/django/compta/comptes/')
        self.assertEqual(resp.status_code, 200)
        numeros = {r['numero'] for r in rows(resp)}
        self.assertIn('3421', numeros)
        # Tous les comptes appartiennent à la société A.
        for r in rows(resp):
            self.assertTrue(
                CompteComptable.objects.filter(
                    id=r['id'], company=self.co_a).exists())

    def test_ecriture_creee_equilibree_et_societe_serveur(self):
        api = auth(self.user_a)
        journal = Journal.objects.get(company=self.co_a, code='VTE')
        clients = services.get_compte(self.co_a, '3421')
        ventes = services.get_compte(self.co_a, '7121')
        payload = {
            'journal': journal.id,
            'date_ecriture': '2026-01-10',
            'libelle': 'Vente test',
            'lignes': [
                {'compte': clients.id, 'debit': '120', 'credit': '0'},
                {'compte': ventes.id, 'debit': '0', 'credit': '120'},
            ],
        }
        resp = api.post('/api/django/compta/ecritures/', payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ecr = EcritureComptable.objects.get(id=resp.data['id'])
        self.assertEqual(ecr.company, self.co_a)  # posée côté serveur
        self.assertTrue(ecr.est_equilibree)

    def test_ecriture_desequilibree_rejetee_api(self):
        api = auth(self.user_a)
        journal = Journal.objects.get(company=self.co_a, code='VTE')
        clients = services.get_compte(self.co_a, '3421')
        ventes = services.get_compte(self.co_a, '7121')
        payload = {
            'journal': journal.id,
            'date_ecriture': '2026-01-10',
            'libelle': 'Déséquilibrée',
            'lignes': [
                {'compte': clients.id, 'debit': '120', 'credit': '0'},
                {'compte': ventes.id, 'debit': '0', 'credit': '90'},
            ],
        }
        resp = api.post('/api/django/compta/ecritures/', payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_ecriture_cross_company_compte_refuse(self):
        # Un utilisateur de A ne peut pas utiliser un compte de B.
        api = auth(self.user_a)
        journal = Journal.objects.get(company=self.co_a, code='VTE')
        compte_b = services.get_compte(self.co_b, '3421')
        ventes_a = services.get_compte(self.co_a, '7121')
        payload = {
            'journal': journal.id,
            'date_ecriture': '2026-01-10',
            'libelle': 'Cross',
            'lignes': [
                {'compte': compte_b.id, 'debit': '120', 'credit': '0'},
                {'compte': ventes_a.id, 'debit': '0', 'credit': '120'},
            ],
        }
        resp = api.post('/api/django/compta/ecritures/', payload, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_ecritures_list_isolation(self):
        # Une écriture chez A n'apparaît jamais chez B.
        journal = Journal.objects.get(company=self.co_a, code='VTE')
        from decimal import Decimal
        services.creer_ecriture(
            self.co_a, journal, date(2026, 1, 1), 'A only',
            [
                {'compte': services.get_compte(self.co_a, '3421'),
                 'debit': Decimal('10'), 'credit': Decimal('0')},
                {'compte': services.get_compte(self.co_a, '7121'),
                 'debit': Decimal('0'), 'credit': Decimal('10')},
            ])
        api_b = auth(self.user_b)
        resp = api_b.get('/api/django/compta/ecritures/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_acces_refuse_role_normal(self):
        co = make_company('api-normal', 'API Normal')
        normal = make_user(co, 'compta-normal', role='normal')
        api = auth(normal)
        resp = api.get('/api/django/compta/comptes/')
        self.assertEqual(resp.status_code, 403)

    def test_etats_balance_endpoint(self):
        api = auth(self.user_a)
        resp = api.get('/api/django/compta/etats/balance/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_debit', resp.data)
        self.assertIn('equilibree', resp.data)

    def test_etats_grand_livre_bilan_cpc_endpoints(self):
        api = auth(self.user_a)
        for path in ('grand_livre', 'bilan', 'cpc'):
            resp = api.get(f'/api/django/compta/etats/{path}/')
            self.assertEqual(resp.status_code, 200, path)
