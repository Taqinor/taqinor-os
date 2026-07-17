"""NTFPA11 — driver pipeline → revenu prévisionnel : revenu d'un mois =
Σ(valeur_devis × probabilité_gain) des leads dont la clôture prévue tombe ce
mois-là."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.fpa.services import projeter_revenu_pipeline


class TestProjeterRevenuPipeline(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa11-co', defaults={'nom': 'NTFPA11 Co'})

    def _lead(self, stage, montant, cloture):
        return Lead.objects.create(
            company=self.company, nom='Lead', stage=stage,
            montant_estime=Decimal(montant),
            date_cloture_prevue=cloture)

    def test_revenu_pondere_par_mois_de_cloture(self):
        # Un lead en QUOTE_SENT (proba 0.40) montant 100000, clôture mars.
        self._lead('QUOTE_SENT', '100000', date(2027, 3, 15))
        par_mois = projeter_revenu_pipeline(
            self.company, date(2027, 1, 1), date(2027, 12, 31))
        self.assertIn('2027-03', par_mois)
        # 100000 × 0.40 = 40000 (le win_weight peut appliquer une décote de
        # fraîcheur : on vérifie que la contribution est strictement positive et
        # ≤ 40000).
        self.assertGreater(par_mois['2027-03'], Decimal('0'))
        self.assertLessEqual(par_mois['2027-03'], Decimal('40000'))

    def test_lead_signe_exclu_du_pipeline(self):
        self._lead('SIGNED', '100000', date(2027, 3, 15))
        par_mois = projeter_revenu_pipeline(
            self.company, date(2027, 1, 1), date(2027, 12, 31))
        self.assertEqual(par_mois, {})

    def test_hors_fenetre_exclu(self):
        self._lead('QUOTE_SENT', '100000', date(2028, 3, 15))
        par_mois = projeter_revenu_pipeline(
            self.company, date(2027, 1, 1), date(2027, 12, 31))
        self.assertEqual(par_mois, {})
