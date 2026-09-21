"""Tests ZACC7 — Rapport d'analyse des frais (pivot employé × catégorie ×
période).

Couvre : l'analyse d'un trimestre rend les totaux par employé et par
catégorie réconciliés avec la liste, une note brouillon est exclue, l'export
xlsx sort, cross-company isolé.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services

User = get_user_model()


def make_company(slug='zacc7-co', nom='ZACC7 Co'):
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
        self.emp1 = make_user(self.company, 'zacc7-emp1', role='commercial')
        self.emp2 = make_user(self.company, 'zacc7-emp2', role='commercial')
        self.note1 = services.creer_note_frais(
            self.company, employe=self.emp1, date_frais=date(2026, 7, 5),
            montant=Decimal('150'), motif='Repas client',
            categorie='repas')
        services.soumettre_note_frais(self.note1)
        self.note2 = services.creer_note_frais(
            self.company, employe=self.emp1, date_frais=date(2026, 7, 10),
            montant=Decimal('300'), motif='Carburant',
            categorie='carburant')
        services.soumettre_note_frais(self.note2)
        self.note3 = services.creer_note_frais(
            self.company, employe=self.emp2, date_frais=date(2026, 7, 15),
            montant=Decimal('80'), motif='Péage', categorie='peage')
        services.soumettre_note_frais(self.note3)
        # Note brouillon : jamais soumise, exclue de l'analyse.
        services.creer_note_frais(
            self.company, employe=self.emp1, date_frais=date(2026, 7, 20),
            montant=Decimal('9999'), motif='Brouillon jamais soumis',
            categorie='autre')


class TestSelector(_Base):
    def test_group_by_employe(self):
        rapport = selectors.analyse_notes_frais(
            self.company, date_debut='2026-07-01', date_fin='2026-07-31',
            group_by='employe')
        self.assertEqual(rapport['total_general'], Decimal('530'))
        totaux = {ligne['cle']: ligne['total'] for ligne in rapport['lignes']}
        self.assertEqual(totaux[self.emp1.id], Decimal('450'))
        self.assertEqual(totaux[self.emp2.id], Decimal('80'))

    def test_group_by_categorie(self):
        rapport = selectors.analyse_notes_frais(
            self.company, group_by='categorie')
        totaux = {ligne['cle']: ligne['total'] for ligne in rapport['lignes']}
        self.assertEqual(totaux['repas'], Decimal('150'))
        self.assertEqual(totaux['carburant'], Decimal('300'))
        self.assertEqual(totaux['peage'], Decimal('80'))

    def test_group_by_mois(self):
        rapport = selectors.analyse_notes_frais(self.company, group_by='mois')
        self.assertEqual(len(rapport['lignes']), 1)
        self.assertEqual(rapport['lignes'][0]['cle'], '2026-07')
        self.assertEqual(rapport['lignes'][0]['total'], Decimal('530'))

    def test_hors_periode_exclu(self):
        rapport = selectors.analyse_notes_frais(
            self.company, date_debut='2026-08-01', date_fin='2026-08-31')
        self.assertEqual(rapport['total_general'], Decimal('0'))

    def test_isolation_societe(self):
        autre = make_company('zacc7-autre', 'Autre Co')
        rapport = selectors.analyse_notes_frais(autre)
        self.assertEqual(rapport['total_general'], Decimal('0'))


class TestEndpoint(_Base):
    def setUp(self):
        super().setUp()
        self.user = make_user(self.company, 'zacc7-admin')
        self.api = auth(self.user)

    def test_endpoint_json(self):
        resp = self.api.get(
            '/api/django/compta/notes-frais/analyse/?group_by=employe')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            Decimal(resp.data['total_general']), Decimal('530'))

    def test_endpoint_xlsx_export(self):
        resp = self.api.get(
            '/api/django/compta/notes-frais/analyse/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
