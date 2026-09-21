"""NTFPA18 — analyse_sensibilite : 9 points (pas de 5 % de -20 à +20) avec le
revenu total recalculé pour chacun (pur stdlib, aucune dépendance)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.fpa.models import CycleBudgetaire
from apps.fpa.services import analyse_sensibilite


class TestAnalyseSensibilite(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ntfpa18-co', defaults={'nom': 'NTFPA18 Co'})
        self.cycle = CycleBudgetaire.objects.create(
            company=self.company, nom='Budget 2027',
            date_debut=date(2027, 1, 1), date_fin=date(2027, 12, 31))
        Lead.objects.create(
            company=self.company, nom='Lead', stage='QUOTE_SENT',
            montant_estime=Decimal('100000'),
            date_cloture_prevue=date(2027, 6, 15))

    def test_neuf_points_de_moins20_a_plus20(self):
        points = analyse_sensibilite(
            self.company, self.cycle.pk, 'taux_conversion', 20)
        self.assertEqual(len(points), 9)
        variations = [p['variation_pct'] for p in points]
        self.assertEqual(variations, [-20, -15, -10, -5, 0, 5, 10, 15, 20])
        # Le point à 0 % = revenu de base ; le point à +20 % > le point à -20 %.
        base = Decimal(points[4]['revenu_total'])
        self.assertGreater(Decimal(points[8]['revenu_total']), Decimal(points[0]['revenu_total']))
        self.assertGreaterEqual(base, Decimal('0'))

    def test_cycle_inconnu_retourne_liste_vide(self):
        self.assertEqual(
            analyse_sensibilite(self.company, 999999, 'taux_conversion', 20), [])
