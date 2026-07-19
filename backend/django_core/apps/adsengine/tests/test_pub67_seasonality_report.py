"""PUB67 — seasonality_report : recommandation de réallocation budgétaire
saisonnière depuis l'historique RÉEL Devis (jamais une action automatique) ;
<12 mois-calendaires distincts -> abstention explicite."""
import datetime
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis

from apps.adsengine import reporting


class SeasonalityReportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PUB67 Report Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='C', prenom='Saison')

    def _signed(self, ref, mode, date_acceptation):
        Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            taux_tva=Decimal('20'), statut=Devis.Statut.ACCEPTE,
            mode_installation=mode, date_acceptation=date_acceptation)

    def test_less_than_12_months_abstains(self):
        self._signed('DEV-PUB6701', 'residentiel', datetime.date(2026, 3, 1))
        result = reporting.seasonality_report(self.company)
        self.assertFalse(result['donnees_suffisantes'])
        self.assertIsNotNone(result['avertissement'])
        self.assertEqual(result['par_mode'], [])

    def test_full_year_coverage_produces_recommendation(self):
        for month in range(1, 13):
            self._signed(
                f'DEV-PUB67-{month:02d}', 'residentiel',
                datetime.date(2025, month, 15))
        # Un pic clair en décembre.
        self._signed('DEV-PUB67-DEC-EXTRA', 'residentiel',
                     datetime.date(2025, 12, 20))
        result = reporting.seasonality_report(self.company)
        self.assertTrue(result['donnees_suffisantes'])
        self.assertIsNone(result['avertissement'])
        mode_row = next(
            r for r in result['par_mode']
            if r['mode_installation'] == 'residentiel')
        self.assertEqual(mode_row['mois_pic'], 12)
        self.assertIn('recommandation seule', mode_row['recommandation_fr'])
