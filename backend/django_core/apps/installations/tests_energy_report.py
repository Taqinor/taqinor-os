"""Tests du rapport de production énergétique ESTIMÉE (N53).

Couvre :
  - le calcul (compute_energy_estimate) renvoie des nombres sains pour une
    entrée connue (kWc × rendement, économies, CO₂) et respecte la surcharge
    manuelle de production / les dates de période ;
  - l'endpoint streame un PDF (200, application/pdf, non vide) pour un chantier
    de la société de l'utilisateur ;
  - l'endpoint renvoie 404 pour un chantier d'une AUTRE société (isolation
    multi-tenant) ;
  - le PDF est généré en mémoire (aucun MinIO requis pour le rendu).

Run :
    DJANGO_SETTINGS_MODULE=erp_agentique.settings.dev \
    python manage.py test apps.installations.tests_energy_report -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.installations.energy_report import (
    compute_energy_estimate, render_energy_report_pdf,
    DEFAULT_RENDEMENT_KWH_PAR_KWC_AN, DEFAULT_TARIF_MAD_PAR_KWH,
    DEFAULT_CO2_KG_PAR_KWH,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company, ref, kwc='6.50'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'rap-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        date_mise_en_service=date(2025, 1, 15),
        puissance_installee_kwc=Decimal(kwc))


class TestComputeEstimate(TestCase):
    def test_kwc_times_rendement_over_12_months(self):
        # 6,5 kWc × 1600 kWh/kWc/an = 10 400 kWh/an sur 12 mois.
        est = compute_energy_estimate(Decimal('6.5'), nb_mois=12)
        self.assertEqual(est['production_annuelle_kwh'], Decimal('10400'))
        self.assertEqual(est['production_kwh'], Decimal('10400'))
        # Économies = 10 400 × tarif défaut (1,40) = 14 560 MAD.
        expected_eco = (Decimal('10400') * DEFAULT_TARIF_MAD_PAR_KWH)
        self.assertEqual(est['economies_mad'], expected_eco.quantize(Decimal('0.01')))
        # CO₂ = 10 400 × 0,81 = 8 424 kg = 8,424 t.
        self.assertEqual(est['co2_kg'], Decimal('8424'))
        self.assertEqual(est['co2_tonnes'], Decimal('8.424'))
        # Hypothèses retenues = défauts.
        self.assertEqual(est['rendement_kwh_par_kwc_an'],
                         DEFAULT_RENDEMENT_KWH_PAR_KWC_AN)
        self.assertEqual(est['tarif_mad_par_kwh'], DEFAULT_TARIF_MAD_PAR_KWH)
        self.assertEqual(est['co2_kg_par_kwh'], DEFAULT_CO2_KG_PAR_KWH)
        self.assertFalse(est['production_manuelle'])

    def test_six_months_halves_production(self):
        est = compute_energy_estimate(Decimal('6.5'), nb_mois=6)
        self.assertEqual(est['production_kwh'], Decimal('5200'))

    def test_manual_annual_production_overrides_kwc(self):
        est = compute_energy_estimate(
            Decimal('6.5'), nb_mois=12, production_annuelle_kwh='9000')
        self.assertTrue(est['production_manuelle'])
        self.assertEqual(est['production_kwh'], Decimal('9000'))

    def test_overridable_assumptions(self):
        est = compute_energy_estimate(
            Decimal('10'), nb_mois=12,
            rendement_kwh_par_kwc_an='1700', tarif_mad_par_kwh='1.20',
            co2_kg_par_kwh='0.70')
        self.assertEqual(est['production_kwh'], Decimal('17000'))
        self.assertEqual(est['economies_mad'], Decimal('20400.00'))
        self.assertEqual(est['co2_kg'], Decimal('11900'))

    def test_date_range_defines_period(self):
        # 1 mois calendaire ≈ 30,44 jours → ~1/12 d'année.
        est = compute_energy_estimate(
            Decimal('12'), date_debut=date(2025, 1, 1),
            date_fin=date(2025, 1, 31))
        # 12 kWc × 1600 = 19 200 kWh/an ; ~1 mois ⇒ nettement < l'année.
        self.assertGreater(est['production_kwh'], Decimal('1400'))
        self.assertLess(est['production_kwh'], Decimal('1800'))

    def test_zero_kwc_yields_zero(self):
        est = compute_energy_estimate(None, nb_mois=12)
        self.assertEqual(est['production_kwh'], Decimal('0'))
        self.assertEqual(est['economies_mad'], Decimal('0.00'))


class TestRenderPdf(TestCase):
    def test_render_returns_pdf_bytes_in_memory(self):
        company = make_company('rap-co-a', 'Rap Co A')
        inst = make_installation(company, 'CHT-RAP-A1')
        pdf = render_energy_report_pdf(inst, {'nb_mois': 12})
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf), 1000)


class TestEnergyReportEndpoint(TestCase):
    def setUp(self):
        self.company_a = make_company('rap-co-a2', 'Rap Co A2')
        self.company_b = make_company('rap-co-b2', 'Rap Co B2')
        self.user_a = User.objects.create_user(
            username='rap_a', password='x', role_legacy='responsable',
            company=self.company_a)
        self.api = auth(self.user_a)
        self.inst_a = make_installation(self.company_a, 'CHT-RAP-EP-A')
        self.inst_b = make_installation(self.company_b, 'CHT-RAP-EP-B')

    def _url(self, inst):
        return f'/api/django/installations/chantiers/{inst.id}/rapport-energie/'

    def test_returns_pdf_for_in_company_installation(self):
        r = self.api.get(self._url(self.inst_a), {'nb_mois': 12})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        content = b''.join(r.streaming_content) if getattr(
            r, 'streaming', False) else r.content
        self.assertTrue(content.startswith(b'%PDF'))
        self.assertGreater(len(content), 1000)

    def test_accepts_manual_and_tariff_overrides(self):
        r = self.api.get(
            self._url(self.inst_a),
            {'production_annuelle_kwh': '9000', 'tarif': '1.5', 'nb_mois': 12})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_404_for_other_company_installation(self):
        r = self.api.get(self._url(self.inst_b), {'nb_mois': 12})
        self.assertEqual(r.status_code, 404)
