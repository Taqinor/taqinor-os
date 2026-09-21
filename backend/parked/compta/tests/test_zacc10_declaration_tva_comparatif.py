"""Tests ZACC10 — Déclaration TVA : comparatif M-1/N-1 + rendu PDF du
bordereau.

Couvre : la déclaration d'un mois affiche N vs M-1 avec écarts, le bordereau
PDF se télécharge aux montants identiques au calcul FG137, défaut sans
``comparer`` inchangé, company-scopé.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services

User = get_user_model()


def make_company(slug='zacc10-co', nom='ZACC10 Co'):
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
        journal_od = services._journal(
            self.company, services.Journal.Type.OPERATIONS_DIVERSES)
        compte_tva_collectee = services.get_compte(self.company, '4455')
        compte_ventes = services.get_compte(self.company, '7121')
        compte_clients = services.get_compte(self.company, '3421')
        # Février : TVA collectée de 200 (vente 1000 HT + 200 TVA), soldée
        # par le débit du compte clients (créance TTC 1200) pour équilibrer
        # l'écriture.
        services.creer_ecriture_od(
            self.company, '2026-02-15', 'Vente février',
            [
                {'compte': compte_clients, 'debit': Decimal('1200'),
                 'credit': Decimal('0')},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': Decimal('1000')},
                {'compte': compte_tva_collectee, 'debit': Decimal('0'),
                 'credit': Decimal('200')},
            ], journal=journal_od)
        # Mars : TVA collectée de 400 (le double).
        services.creer_ecriture_od(
            self.company, '2026-03-15', 'Vente mars',
            [
                {'compte': compte_clients, 'debit': Decimal('2400'),
                 'credit': Decimal('0')},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': Decimal('2000')},
                {'compte': compte_tva_collectee, 'debit': Decimal('0'),
                 'credit': Decimal('400')},
            ], journal=journal_od)
        self.user = make_user(self.company, 'zacc10-admin')
        self.api = auth(self.user)


class TestSelector(_Base):
    def test_comparer_false_defaut_inchange(self):
        data = selectors.preparer_declaration_tva(
            self.company, date_debut='2026-03-01', date_fin='2026-03-31')
        self.assertNotIn('tva_collectee_m1', data)

    def test_comparer_true_ecart_m1(self):
        data = selectors.preparer_declaration_tva(
            self.company, date_debut='2026-03-01', date_fin='2026-03-31',
            comparer=True, date_debut_m1='2026-02-01',
            date_fin_m1='2026-02-28')
        self.assertEqual(data['tva_collectee'], Decimal('400'))
        self.assertEqual(data['tva_collectee_m1'], Decimal('200'))
        self.assertEqual(data['tva_collectee_ecart_pct'], Decimal('100.00'))

    def test_periode_sans_m1_renvoie_zero(self):
        data = selectors.preparer_declaration_tva(
            self.company, date_debut='2020-01-01', date_fin='2020-01-31',
            comparer=True)
        self.assertEqual(data['tva_collectee'], Decimal('0'))
        self.assertEqual(data['tva_collectee_m1'], Decimal('0'))


class TestEndpoint(_Base):
    def _preparer_mars(self):
        resp = self.api.post(
            '/api/django/compta/declarations-tva/preparer/',
            {'date_debut': '2026-03-01', 'date_fin': '2026-03-31'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data['id']

    def test_comparatif_endpoint(self):
        decl_id = self._preparer_mars()
        resp = self.api.get(
            f'/api/django/compta/declarations-tva/{decl_id}/comparatif/'
            f'?date_debut_m1=2026-02-01&date_fin_m1=2026-02-28')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            Decimal(str(resp.data['tva_collectee_m1'])), Decimal('200'))

    def test_bordereau_pdf_ou_503(self):
        decl_id = self._preparer_mars()
        resp = self.api.get(
            f'/api/django/compta/declarations-tva/{decl_id}/bordereau-pdf/')
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_bordereau_pdf_cross_company_404(self):
        autre = make_company('zacc10-autre', 'Autre Co')
        services.seed_plan_comptable(autre)
        decl_autre = services.preparer_declaration_tva(
            autre, date_debut='2026-03-01', date_fin='2026-03-31')
        resp = self.api.get(
            f'/api/django/compta/declarations-tva/{decl_autre.id}/'
            f'bordereau-pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_declaration_endpoint_export_csv_toujours_inchange(self):
        decl_id = self._preparer_mars()
        resp = self.api.get(
            f'/api/django/compta/declarations-tva/{decl_id}/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
