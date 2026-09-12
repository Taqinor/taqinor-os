"""NTNRG26 — Attestation carbone PDF certifiable, par site et consolidée client.

Couvre :
  * un site avec production mesurée → PDF avec chiffres + méthodologie ;
  * un site SANS relevé → message propre dans le PDF, jamais une erreur ;
  * un client multi-sites → attestation CONSOLIDÉE (cumul de ses systèmes) ;
  * les deux endpoints (site / client) répondent en `application/pdf`.

Run :
    python manage.py test apps.monitoring.test_ntnrg26_attestation_carbone -v 2
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
from apps.monitoring.models import MonitoringConfig, ProductionReading

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestCarbonReportDataSite(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg26-co', defaults={'nom': 'NTNRG26 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='Carbone',
            email='ntnrg26-cli@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='NTNRG26-1', client=self.client_obj,
            puissance_installee_kwc=Decimal('10'))

    def test_no_reading_has_no_data_but_no_error(self):
        from apps.monitoring.report_carbon import build_carbon_report_data_site
        data = build_carbon_report_data_site(self.inst, today=date(2026, 6, 30))
        self.assertFalse(data['has_data'])
        self.assertEqual(data['production_kwh'], Decimal('0.00'))
        self.assertIn('méthodologie', str(data['methodologie']).lower())

    def test_with_reading_has_data_and_co2(self):
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 6, 1), energy_kwh=Decimal('1000'))
        from apps.monitoring.report_carbon import build_carbon_report_data_site
        data = build_carbon_report_data_site(self.inst, today=date(2026, 6, 30))
        self.assertTrue(data['has_data'])
        self.assertEqual(data['production_kwh'], Decimal('1000.00'))
        self.assertGreater(data['co2_kg'], Decimal('0'))

    def test_render_html_shows_methodology_and_no_crash_without_data(self):
        from apps.monitoring.report_carbon import build_carbon_report_data_site, _build_html
        data = build_carbon_report_data_site(self.inst, today=date(2026, 6, 30))
        html = _build_html(data, entreprise_nom='NTNRG26 Co')
        self.assertIn('Méthodologie', html)
        self.assertIn('Aucune production mesurée', html)

    def test_render_pdf_bytes_without_data(self):
        from apps.monitoring.report_carbon import render_carbon_report_pdf_site
        pdf_bytes = render_carbon_report_pdf_site(self.inst, today=date(2026, 6, 30))
        self.assertTrue(bytes(pdf_bytes).startswith(b'%PDF'))


class TestCarbonReportDataClient(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg26-client-co', defaults={'nom': 'NTNRG26 Client Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Multi', prenom='Site',
            email='ntnrg26-multi@example.invalid')
        self.inst1 = Installation.objects.create(
            company=self.company, reference='NTNRG26-C1', client=self.client_obj,
            puissance_installee_kwc=Decimal('5'))
        self.inst2 = Installation.objects.create(
            company=self.company, reference='NTNRG26-C2', client=self.client_obj,
            puissance_installee_kwc=Decimal('5'))
        ProductionReading.objects.create(
            company=self.company, installation=self.inst1,
            date=date(2026, 6, 1), energy_kwh=Decimal('300'))
        ProductionReading.objects.create(
            company=self.company, installation=self.inst2,
            date=date(2026, 6, 1), energy_kwh=Decimal('200'))

    def test_consolidated_sums_all_client_systems(self):
        from apps.monitoring.report_carbon import build_carbon_report_data_client
        data = build_carbon_report_data_client(
            self.company, self.client_obj.id, today=date(2026, 6, 30))
        self.assertTrue(data['has_data'])
        self.assertEqual(data['production_kwh'], Decimal('500.00'))
        self.assertEqual(data['systems_count'], 2)


class TestCarbonReportEndpoints(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntnrg26-view-co', defaults={'nom': 'NTNRG26 View Co'})
        self.user = User.objects.create_user(
            username='ntnrg26_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cli', prenom='View',
            email='ntnrg26-view@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='NTNRG26-V', client=self.client_obj,
            puissance_installee_kwc=Decimal('10'))
        self.config = MonitoringConfig.objects.create(
            company=self.company, installation=self.inst)

    def test_site_endpoint_returns_pdf(self):
        r = self.api.get(
            f'/api/django/monitoring/configs/{self.config.id}/attestation-carbone-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_client_endpoint_requires_client_param(self):
        r = self.api.get(
            '/api/django/monitoring/configs/attestation-carbone-client-pdf/')
        self.assertEqual(r.status_code, 400)

    def test_client_endpoint_returns_pdf(self):
        r = self.api.get(
            '/api/django/monitoring/configs/attestation-carbone-client-pdf/'
            f'?client={self.client_obj.id}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
