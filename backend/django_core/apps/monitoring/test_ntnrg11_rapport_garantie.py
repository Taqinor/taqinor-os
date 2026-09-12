"""NTNRG11 — Rapport CONTRACTUEL mensuel de garantie de performance (PDF).

Couvre :
  * pas de garantie configurée → `build_warranty_report_data` no-op gracieux
    (`has_warranty=False`) et l'endpoint répond 404 propre (pas de PDF vide) ;
  * tableau mensuel avec écart et pénalité CUMULÉE (jamais un écart par mois
    isolé qui ferait mentir la compensation contractuelle réelle) ;
  * mention légale présente dans le PDF, distinct du rapport O&M générique.

Run :
    python manage.py test apps.monitoring.test_ntnrg11_rapport_garantie -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.monitoring.models import (
    MonitoringConfig, ProductionReading, ProductionWarranty,
)

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestWarrantyReportData(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg11-co', defaults={'nom': 'NTNRG11 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='Garantie',
            email='ntnrg11-cli@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='NTNRG11-1', client=self.client_obj,
            puissance_installee_kwc=Decimal('10'))
        self.today = date(2026, 6, 30)

    def test_no_warranty_is_graceful_noop(self):
        from apps.monitoring.report_warranty import build_warranty_report_data
        data = build_warranty_report_data(self.inst, today=self.today)
        self.assertFalse(data['has_warranty'])

    def test_monthly_table_cumulative_shortfall_and_penalty(self):
        ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'),
            start_year=2026, tolerance_pct=Decimal('0'),
            compensation_mad_per_kwh=Decimal('1'))
        # Production très en dessous du garanti chaque mois → manque cumulé.
        for month in (1, 2, 3, 4, 5, 6):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst,
                date=date(2026, month, 5), period_days=30,
                energy_kwh=Decimal('100'))
        from apps.monitoring.report_warranty import build_warranty_report_data
        data = build_warranty_report_data(
            self.inst, year=2026, today=self.today)
        self.assertTrue(data['has_warranty'])
        # Juin est le mois en cours (30/06) → 6 mois dans le tableau.
        self.assertEqual(len(data['monthly']), 6)
        self.assertEqual(data['monthly'][0]['month'], 1)
        self.assertEqual(data['monthly'][-1]['month'], 6)
        # Écart et pénalité croissent avec le manque cumulé (jamais négatifs).
        for m in data['monthly']:
            self.assertGreaterEqual(m['ecart_cumule_kwh'], Decimal('0'))
            self.assertGreaterEqual(m['penalite_cumulee_mad'], Decimal('0'))
        self.assertGreater(
            data['monthly'][-1]['penalite_cumulee_mad'], Decimal('0'))
        # Le total exposé est celui du DERNIER mois du tableau (cumulé).
        self.assertEqual(
            data['total_penalite_mad'], data['monthly'][-1]['penalite_cumulee_mad'])
        self.assertTrue(data['year_in_progress'])

    def test_tolerance_absorbs_small_shortfall(self):
        ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'),
            start_year=2026, tolerance_pct=Decimal('100'),
            compensation_mad_per_kwh=Decimal('1'))
        from apps.monitoring.report_warranty import build_warranty_report_data
        data = build_warranty_report_data(
            self.inst, year=2026, today=self.today)
        # Tolérance à 100 % → jamais de pénalité, quel que soit le manque.
        for m in data['monthly']:
            self.assertEqual(m['penalite_cumulee_mad'], Decimal('0.00'))

    def test_closed_year_is_not_in_progress(self):
        ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'),
            start_year=2024, tolerance_pct=Decimal('5'))
        from apps.monitoring.report_warranty import build_warranty_report_data
        data = build_warranty_report_data(
            self.inst, year=2025, today=self.today)
        self.assertFalse(data['year_in_progress'])
        self.assertEqual(len(data['monthly']), 12)


class TestWarrantyReportHtmlAndPdf(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg11-pdf-co', defaults={'nom': 'NTNRG11 PDF Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='PDF',
            email='ntnrg11-pdf@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='NTNRG11-PDF', client=self.client_obj,
            puissance_installee_kwc=Decimal('10'))
        self.today = date(2026, 6, 30)
        ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'),
            start_year=2026, tolerance_pct=Decimal('5'),
            compensation_mad_per_kwh=Decimal('1.5'))

    def test_html_contains_legal_mention_and_is_distinct_from_om(self):
        from apps.monitoring.report_warranty import (
            build_warranty_report_data, build_warranty_report_html,
        )
        data = build_warranty_report_data(
            self.inst, year=2026, today=self.today)
        html = build_warranty_report_html(data, entreprise_nom='NTNRG11 PDF Co')
        self.assertIn('clause contractuelle', html)
        self.assertIn('Pénalité cumulée', html)
        # Distinct du gabarit du rapport O&M générique (aucune section
        # « Recommandations » — propre au rapport O&M).
        self.assertNotIn('Recommandations', html)

    def test_render_pdf_bytes(self):
        from apps.monitoring.report_warranty import render_warranty_report_pdf
        pdf_bytes = render_warranty_report_pdf(
            self.inst, year=2026, today=self.today)
        self.assertTrue(pdf_bytes)
        self.assertTrue(bytes(pdf_bytes).startswith(b'%PDF'))


class TestWarrantyReportEndpoint(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg11-view-co', defaults={'nom': 'NTNRG11 View Co'})
        self.user = User.objects.create_user(
            username='ntnrg11_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='View',
            email='ntnrg11-view@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='NTNRG11-V', client=self.client_obj,
            puissance_installee_kwc=Decimal('10'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst)

    def test_endpoint_404_without_warranty(self):
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.id}/rapport-garantie-pdf/')
        self.assertEqual(r.status_code, 404)

    def test_endpoint_returns_pdf_with_warranty(self):
        ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'),
            start_year=2026, tolerance_pct=Decimal('5'))
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.id}/rapport-garantie-pdf/'
            '?annee=2026')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
