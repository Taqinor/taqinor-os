"""Tests XACC35 — Attestations de retenue à la source par prestataire (PDF).

Couvre : l'attestation d'un versement et le cumul annuel d'un prestataire se
téléchargent avec les bons montants (chiffres = ledger FG139 à l'identique),
company-scopé, tests de rendu HTML (le contenu, avant passage WeasyPrint).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.pdf_ras import (
    render_attestation_annuelle_html,
    render_attestation_retenue_html,
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


class AttestationHtmlTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc35-svc', 'XACC35 Svc')
        self.user = make_user(self.co, 'xacc35-svc-user')

    def test_attestation_versement_contient_montants_identiques(self):
        ras = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 6, 15), base=Decimal('10000'),
            taux=Decimal('10'), tiers_nom='Cabinet Fiscal SARL',
            identifiant_fiscal='001234567000012', piece='FF-2026-042',
            user=self.user)
        html = render_attestation_retenue_html(ras)
        self.assertIn('Cabinet Fiscal SARL', html)
        self.assertIn('001234567000012', html)
        self.assertIn('1 000,00', html)  # montant retenu = 10000 * 10% = 1000.
        self.assertIn('10 000,00', html)  # base.

    def test_attestation_annuelle_cumule_plusieurs_pieces(self):
        r1 = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 3, 1), base=Decimal('5000'),
            taux=Decimal('10'), tiers_nom='Consultant X',
            tiers_id=42, piece='FF-1', user=self.user)
        r2 = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 9, 1), base=Decimal('8000'),
            taux=Decimal('10'), tiers_nom='Consultant X',
            tiers_id=42, piece='FF-2', user=self.user)
        html = render_attestation_annuelle_html(
            [r1, r2], 'Consultant X', 2026)
        self.assertIn('Consultant X', html)
        self.assertIn('2026', html)
        # Total retenu = 500 + 800 = 1300.
        self.assertIn('1 300,00', html)
        self.assertIn('FF-1', html)
        self.assertIn('FF-2', html)

    def test_entete_societe_optionnelle(self):
        ras = services.enregistrer_retenue_source(
            self.co, date_piece=date(2026, 6, 15), base=Decimal('1000'),
            taux=Decimal('10'), tiers_nom='X', user=self.user)
        # Sans profil société : ne lève jamais.
        html = render_attestation_retenue_html(ras, None)
        self.assertIn('Attestation de retenue à la source', html)


class AttestationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xacc35-a', 'XACC35 A')
        self.co_b = make_company('xacc35-b', 'XACC35 B')
        self.user_a = make_user(self.co_a, 'xacc35-user-a')

    def test_attestation_versement_endpoint_pdf(self):
        ras = services.enregistrer_retenue_source(
            self.co_a, date_piece=date(2026, 6, 15), base=Decimal('2000'),
            taux=Decimal('10'), tiers_nom='Y', user=self.user_a)
        resp = auth(self.user_a).get(
            f'/api/django/compta/retenues-source/{ras.id}/attestation/')
        # 200 (PDF) si weasyprint dispo, sinon 503 explicite — jamais 500/404.
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_attestation_cross_company_404(self):
        ras_b = services.enregistrer_retenue_source(
            self.co_b, date_piece=date(2026, 6, 15), base=Decimal('2000'),
            taux=Decimal('10'), tiers_nom='Z',
            user=make_user(self.co_b, 'xacc35-user-b'))
        resp = auth(self.user_a).get(
            f'/api/django/compta/retenues-source/{ras_b.id}/attestation/')
        self.assertEqual(resp.status_code, 404)

    def test_attestation_annuelle_endpoint(self):
        services.enregistrer_retenue_source(
            self.co_a, date_piece=date(2026, 4, 1), base=Decimal('3000'),
            taux=Decimal('10'), tiers_nom='Consultant Annuel', tiers_id=99,
            user=self.user_a)
        resp = auth(self.user_a).get(
            '/api/django/compta/retenues-source/attestation-annuelle/',
            {'tiers': 99, 'annee': 2026})
        self.assertIn(resp.status_code, (200, 503))

    def test_attestation_annuelle_sans_resultat_404(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/retenues-source/attestation-annuelle/',
            {'tiers': 999999, 'annee': 2026})
        self.assertEqual(resp.status_code, 404)

    def test_attestation_annuelle_parametres_manquants_400(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/retenues-source/attestation-annuelle/')
        self.assertEqual(resp.status_code, 400)

    def test_refuse_role_normal(self):
        normal = make_user(self.co_a, 'xacc35-normal', role='normal')
        ras = services.enregistrer_retenue_source(
            self.co_a, date_piece=date(2026, 6, 15), base=Decimal('1000'),
            taux=Decimal('10'), tiers_nom='X', user=self.user_a)
        resp = auth(normal).get(
            f'/api/django/compta/retenues-source/{ras.id}/attestation/')
        self.assertEqual(resp.status_code, 403)
