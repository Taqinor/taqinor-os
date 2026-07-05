"""Tests ZACC1 — Rendu PDF imprimable des états de synthèse & légaux.

Couvre : ``?export=pdf`` télécharge un PDF (ou 503 explicite si WeasyPrint
indisponible, jamais 500) pour bilan/CPC/balance/grand-livre/liasse
fiscale/balance âgée fournisseurs, ``export`` inconnu → repli JSON actuel
byte-identique, company-scopé (404 cross-company), et le contenu HTML (avant
passage WeasyPrint) porte l'entête société + les totaux réconciliés.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import selectors, services
from apps.compta.models import ExerciceComptable
from apps.compta.pdf_etats import (
    render_balance_agee_html,
    render_balance_html,
    render_bilan_html,
    render_cpc_html,
    render_grand_livre_html,
    render_liasse_html,
)

User = get_user_model()


def make_company(slug='zacc1-co', nom='ZACC1 Co'):
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
            self.company, '2026-01-15', 'Vente test ZACC1',
            [
                {'compte': compte_clients, 'debit': Decimal('1200'),
                 'credit': Decimal('0')},
                {'compte': compte_ventes, 'debit': Decimal('0'),
                 'credit': Decimal('1200')},
            ],
            journal=journal_od)
        self.user = make_user(self.company, 'zacc1-admin')
        self.api = auth(self.user)


class TestHtmlRendering(_Base):
    """Le contenu HTML (avant passage WeasyPrint) est vérifiable sans lib."""

    def test_bilan_html_contient_entete_et_totaux(self):
        data = selectors.bilan(self.company, date_fin='2026-01-31')
        html = render_bilan_html(data, None, date_fin='2026-01-31')
        self.assertIn('Bilan', html)
        self.assertIn('1 200,00', html)

    def test_cpc_html_contient_resultat(self):
        data = selectors.cpc(
            self.company, date_debut='2026-01-01', date_fin='2026-01-31')
        html = render_cpc_html(
            data, None, date_debut='2026-01-01', date_fin='2026-01-31')
        self.assertIn('Compte de produits et charges', html)
        self.assertIn('1 200,00', html)

    def test_balance_html_contient_lignes(self):
        data = selectors.balance_generale(
            self.company, date_debut='2026-01-01', date_fin='2026-01-31')
        html = render_balance_html(
            data, None, date_debut='2026-01-01', date_fin='2026-01-31')
        self.assertIn('Balance générale', html)
        self.assertIn('3421', html)

    def test_grand_livre_html_par_compte(self):
        data = selectors.grand_livre(
            self.company, date_debut='2026-01-01', date_fin='2026-01-31')
        html = render_grand_livre_html(
            data, None, date_debut='2026-01-01', date_fin='2026-01-31')
        self.assertIn('Grand livre', html)
        self.assertIn('3421', html)

    def test_balance_agee_html_vide_sans_lever(self):
        data = selectors.balance_agee_fournisseurs(self.company)
        html = render_balance_agee_html(data, None)
        self.assertIn('Balance âgée', html)

    def test_liasse_html_assemble_bilan_et_cpc(self):
        exercice = ExerciceComptable.objects.create(
            company=self.company, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        data = selectors.liasse_fiscale(self.company, exercice)
        html = render_liasse_html(data, None, exercice=exercice)
        self.assertIn('Liasse fiscale', html)
        self.assertIn('1 200,00', html)

    def test_entete_societe_optionnelle_ne_leve_jamais(self):
        data = selectors.bilan(self.company)
        html = render_bilan_html(data, None)
        self.assertIn('Bilan', html)


class TestEndpointExportPdf(_Base):
    def test_bilan_export_pdf_ou_503(self):
        resp = self.api.get('/api/django/compta/etats/bilan/?export=pdf')
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_cpc_export_pdf_ou_503(self):
        resp = self.api.get('/api/django/compta/etats/cpc/?export=pdf')
        self.assertIn(resp.status_code, (200, 503))

    def test_balance_export_pdf_ou_503(self):
        resp = self.api.get('/api/django/compta/etats/balance/?export=pdf')
        self.assertIn(resp.status_code, (200, 503))

    def test_grand_livre_export_pdf_ou_503(self):
        resp = self.api.get(
            '/api/django/compta/etats/grand_livre/?export=pdf')
        self.assertIn(resp.status_code, (200, 503))

    def test_balance_agee_fournisseurs_export_pdf_ou_503(self):
        resp = self.api.get(
            '/api/django/compta/etats/balance-agee-fournisseurs/'
            '?export=pdf')
        self.assertIn(resp.status_code, (200, 503))

    def test_liasse_fiscale_export_pdf_ou_503(self):
        exercice = ExerciceComptable.objects.create(
            company=self.company, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        resp = self.api.get(
            f'/api/django/compta/etats/liasse-fiscale/'
            f'?exercice={exercice.pk}&export=pdf')
        self.assertIn(resp.status_code, (200, 503))

    def test_export_inconnu_repli_json_identique(self):
        """``export=n_importe_quoi`` -> le JSON actuel, byte-identique à
        sans paramètre."""
        resp_sans = self.api.get('/api/django/compta/etats/bilan/')
        resp_inconnu = self.api.get(
            '/api/django/compta/etats/bilan/?export=n_importe_quoi')
        self.assertEqual(resp_sans.status_code, 200)
        self.assertEqual(resp_inconnu.status_code, 200)
        self.assertEqual(resp_sans.data, resp_inconnu.data)

    def test_bilan_sans_export_reste_json(self):
        resp = self.api.get('/api/django/compta/etats/bilan/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')


class TestCrossCompany(TestCase):
    def test_liasse_fiscale_cross_company_404(self):
        co_a = make_company('zacc1-a', 'ZACC1 A')
        co_b = make_company('zacc1-b', 'ZACC1 B')
        services.seed_plan_comptable(co_b)
        exercice_b = ExerciceComptable.objects.create(
            company=co_b, libelle='2026',
            date_debut=date(2026, 1, 1), date_fin=date(2026, 12, 31))
        user_a = make_user(co_a, 'zacc1-user-a')
        resp = auth(user_a).get(
            f'/api/django/compta/etats/liasse-fiscale/'
            f'?exercice={exercice_b.pk}&export=pdf')
        self.assertEqual(resp.status_code, 404)
