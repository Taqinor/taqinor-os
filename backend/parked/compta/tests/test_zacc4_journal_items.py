"""Tests ZACC4 — Vue « Journal Items » : ledger plat ligne-à-ligne
filtrable/exportable de toutes les lignes d'écriture.

Couvre : filtrer par journal+période renvoie les seules lignes concernées
avec Σdébit=Σcrédit sur écritures validées, l'export xlsx/csv sort, un
compte cross-company n'apparaît jamais, pagination, filtres tiers/lettrage.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services

User = get_user_model()


def make_company(slug='zacc4-co', nom='ZACC4 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        services.seed_plan_comptable(self.company)
        services.seed_journaux(self.company)
        compte_clients = services.get_compte(self.company, '3421')
        compte_ventes = services.get_compte(self.company, '7121')
        journal_od = services._journal(
            self.company, services.Journal.Type.OPERATIONS_DIVERSES)
        self.ecriture = services.creer_ecriture_od(
            self.company, '2026-07-01', 'Test ZACC4',
            [
                {'compte': compte_clients, 'debit': Decimal('1000'),
                 'credit': Decimal('0'), 'tiers_type': 'client',
                 'tiers_id': 42},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': Decimal('1000')},
            ],
            journal=journal_od)


class TestSelector(_Base):
    def test_filtre_par_journal_et_periode(self):
        lignes = selectors.journal_items(
            self.company, journal='OD',
            date_debut='2026-07-01', date_fin='2026-07-01')
        self.assertEqual(len(lignes), 2)
        total_debit = sum((ligne['debit'] for ligne in lignes), Decimal('0'))
        total_credit = sum(
            (ligne['credit'] for ligne in lignes), Decimal('0'))
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('1000'))

    def test_hors_periode_vide(self):
        lignes = selectors.journal_items(
            self.company, date_debut='2026-08-01', date_fin='2026-08-31')
        self.assertEqual(lignes, [])

    def test_filtre_par_tiers(self):
        lignes = selectors.journal_items(
            self.company, tiers_type='client', tiers_id=42)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['compte_numero'], '3421')

    def test_filtre_validees(self):
        lignes = selectors.journal_items(self.company, validees=True)
        self.assertEqual(len(lignes), 2)
        lignes_non_validees = selectors.journal_items(
            self.company, validees=False)
        self.assertEqual(lignes_non_validees, [])

    def test_filtre_lettrage_non_lettrees(self):
        lignes = selectors.journal_items(self.company, lettrage='non_lettrees')
        self.assertEqual(len(lignes), 2)
        lignes_lettrees = selectors.journal_items(
            self.company, lettrage='lettrees')
        self.assertEqual(lignes_lettrees, [])

    def test_isolation_societe(self):
        autre = make_company('zacc4-autre', 'Autre Co')
        lignes = selectors.journal_items(autre)
        self.assertEqual(lignes, [])


class TestEndpoint(_Base):
    def setUp(self):
        super().setUp()
        self.user = make_user(self.company, 'zacc4-admin')
        self.api = auth(self.user)

    def test_endpoint_json_pagine(self):
        resp = self.api.get('/api/django/compta/etats/journal-items/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['count'], 2)
        self.assertEqual(len(resp.data['results']), 2)

    def test_endpoint_pagination_limit(self):
        resp = self.api.get(
            '/api/django/compta/etats/journal-items/?limit=1&offset=0')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['count'], 2)

    def test_endpoint_export_csv(self):
        resp = self.api.get(
            '/api/django/compta/etats/journal-items/?export=csv')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')

    def test_endpoint_export_xlsx(self):
        resp = self.api.get(
            '/api/django/compta/etats/journal-items/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
