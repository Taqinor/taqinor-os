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
        # AMON40 — un relevé au 01/01 : la période couverte est l'année.
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 1, 1), period_days=1, energy_kwh=Decimal('1'))
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

    def _garantie_2026(self):
        return ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'), start_year=2026,
            tolerance_pct=Decimal('5'),
            compensation_mad_per_kwh=Decimal('1.10'))

    def test_sans_releve_penalite_non_mesuree(self):
        """AMON104 — année sans aucun relevé : réel, écart et pénalité NON
        mesurés (null, « — » au PDF), jamais « 10 787,84 MAD » sur un réel
        0 ; un relevé de l'année : chiffres mesurés."""
        from apps.monitoring.report_warranty import (
            build_warranty_report_data, build_warranty_report_html,
        )
        self._garantie_2026()
        edition = date(2026, 11, 10)
        data = build_warranty_report_data(self.inst, year=2026, today=edition)
        for cle in ('total_actual_kwh', 'total_ecart_kwh',
                    'total_penalite_mad'):
            self.assertIsNone(data[cle], cle)
        for mois in data['monthly']:
            self.assertIsNone(mois['actual_cumule_kwh'])
            self.assertIsNone(mois['ecart_cumule_kwh'])
            self.assertIsNone(mois['penalite_cumulee_mad'])
        html = build_warranty_report_html(data)
        self.assertIn('— MAD', html)
        self.assertNotIn('10787.84', html)
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2026, 1, 1), period_days=1, energy_kwh=Decimal('30'))
        data = build_warranty_report_data(self.inst, year=2026, today=edition)
        self.assertIsNotNone(data['total_penalite_mad'])
        self.assertIsNotNone(data['monthly'][0]['actual_cumule_kwh'])

    def test_releves_arretes_garanti_borne(self):
        """AMON105 — relevés au garanti du 01/01 au 30/06 : à l'édition du
        10/11, garanti borné au dernier jour couvert ⇒ compensation 0,00 (et
        non 3 857,73), garanti cumulé figé au 30/06 de juillet à novembre ;
        année close entièrement relevée : garanti annuel complet."""
        from datetime import timedelta

        from apps.monitoring.report_warranty import build_warranty_report_data
        from apps.monitoring.services import (
            attendu_entre, production_warranty_status,
        )
        self._garantie_2026()
        jour = date(2026, 1, 1)
        while jour <= date(2026, 6, 30):
            # AMON107 — « au garanti » = au profil mensuel, pas à plat.
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                period_days=1,
                energy_kwh=attendu_entre(12000, jour, jour).quantize(
                    Decimal('0.01')))
            jour += timedelta(days=1)
        edition = date(2026, 11, 10)
        st = production_warranty_status(self.inst, year=2026, today=edition)
        self.assertEqual(st['compensation_mad'], Decimal('0.00'))
        data = build_warranty_report_data(self.inst, year=2026, today=edition)
        self.assertEqual(data['total_penalite_mad'], Decimal('0.00'))
        juin = data['monthly'][5]['guaranteed_cumule_kwh']
        for mois in data['monthly'][6:]:
            self.assertEqual(mois['guaranteed_cumule_kwh'], juin)
        while jour <= date(2026, 12, 31):
            ProductionReading.objects.create(
                company=self.company, installation=self.inst, date=jour,
                period_days=1, energy_kwh=Decimal('32.88'))
            jour += timedelta(days=1)
        st = production_warranty_status(
            self.inst, year=2026, today=date(2027, 1, 10))
        self.assertEqual(st['guaranteed_kwh'], Decimal('12000.00'))

    def test_systeme_au_profil_sans_penalite_ni_recours(self):
        """AMON107 (D-AMON-3) — garanti prorata au PROFIL MENSUEL de
        l'attendu, jamais jours / jours de l'année : un système produisant
        exactement au profil n'a ni pénalité ni « recours fabricant » au
        31/01 comme au 13/05 ; au 31/12 le garanti égale l'annuel complet."""
        from datetime import timedelta

        from apps.monitoring.report import build_om_report_data
        from apps.monitoring.services import (
            attendu_entre, production_warranty_status, warranty_curve_overlay,
        )
        self._garantie_2026()
        jour = date(2026, 1, 1)
        for fin in (date(2026, 1, 31), date(2026, 5, 13)):
            while jour <= fin:
                ProductionReading.objects.create(
                    company=self.company, installation=self.inst, date=jour,
                    period_days=1,
                    energy_kwh=attendu_entre(12000, jour, jour).quantize(
                        Decimal('0.01')))
                jour += timedelta(days=1)
            st = production_warranty_status(self.inst, year=2026, today=fin)
            self.assertEqual(st['compensation_mad'], Decimal('0.00'), fin)
            self.assertTrue(st['within_tolerance'], fin)
            self.assertAlmostEqual(
                float(st['guaranteed_kwh']),
                float(attendu_entre(12000, date(2026, 1, 1), fin)), delta=0.01)
            ov = warranty_curve_overlay(self.inst, today=fin)
            self.assertFalse(ov['manufacturer_recourse'], fin)
            self.assertNotIn(
                'Dérive anormale vs courbe garantie : recours fabricant à '
                'étudier.', build_om_report_data(
                    self.inst, today=fin)['recommendations'])
        st = production_warranty_status(
            self.inst, year=2026, today=date(2026, 12, 31))
        self.assertEqual(st['guaranteed_kwh'], Decimal('12000.00'))

    def test_releve_a_cheval_au_prorata(self):
        """AMON106 — un relevé de 30 j / 300 kWh daté du 07/12/2025 apporte
        50 kWh au réel 2026 et 250 au réel 2025 ; le cumul réel de janvier
        2026 du rapport les compte."""
        from apps.monitoring.report_warranty import build_warranty_report_data
        from apps.monitoring.services import production_for_calendar_year
        ProductionWarranty.objects.create(
            company=self.company, installation=self.inst,
            guaranteed_year1_kwh=Decimal('12000'),
            degradation_pct_per_year=Decimal('0'), start_year=2025,
            tolerance_pct=Decimal('5'),
            compensation_mad_per_kwh=Decimal('1.10'))
        ProductionReading.objects.create(
            company=self.company, installation=self.inst,
            date=date(2025, 12, 7), period_days=30, energy_kwh=Decimal('300'))
        self.assertEqual(production_for_calendar_year(self.inst, 2026),
                         Decimal('50'))
        self.assertEqual(production_for_calendar_year(self.inst, 2025),
                         Decimal('250'))
        data = build_warranty_report_data(
            self.inst, year=2026, today=date(2026, 11, 10))
        self.assertGreaterEqual(data['monthly'][0]['actual_cumule_kwh'],
                                Decimal('50.00'))


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
        # CIQ646 — le rapport de garantie n'existe que pour une société qui a
        # validé l'engagement (CIQ622) : ces cas la valident.
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company=self.company)
        profil.garantie_production_autorisee = True
        profil.garantie_production_validation = 'Juriste, 01/10/2026'
        profil.save()

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
