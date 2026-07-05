"""XCTR16 — Facturation à l'usage depuis le monitoring (kWh supervisés).

Couvre :
  * calcul avec franchise (usage < franchise → 0 facturé, jamais négatif) ;
  * calcul sans franchise (facturable = usage entier) ;
  * période sans lecture disponible → pas de ligne + motif tracé (jamais une
    exception) ;
  * contrat sans `tarif_usage` → comportement actuel inchangé (pas de calcul).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xctr16 -v 2
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models_installation import Installation
from apps.monitoring.models import ProductionReading
from apps.sav.models import ContratMaintenance
from apps.sav.services import calculer_ligne_usage_contrat


def _company(slug='xctr16-co', nom='XCTR16 Co'):
    c, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return c


class XCTR16UsageCalculationTest(TestCase):
    def setUp(self):
        self.co = _company()
        self.other_co = _company(slug='xctr16-other', nom='XCTR16 Autre')
        self.cli = Client.objects.create(
            company=self.co, nom='Client', prenom='XCTR16',
            email='xctr16-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.co, reference='CHT-XCTR16', client=self.cli)
        self.contrat = ContratMaintenance.objects.create(
            company=self.co, client=self.cli, installation=self.inst,
            date_debut=date(2026, 1, 1), actif=True,
            tarif_usage=Decimal('1.5'),
            franchise_incluse=Decimal('100'),
            unite_usage=ContratMaintenance.UniteUsage.KWH)

    def _reading(self, day, kwh, company=None, installation=None):
        ProductionReading.objects.create(
            company=company or self.co, installation=installation or self.inst,
            date=day, energy_kwh=kwh)

    def test_usage_above_franchise_bills_the_excess(self):
        self._reading(date(2026, 3, 5), Decimal('150'))
        montant, description = calculer_ligne_usage_contrat(
            self.contrat, date(2026, 3, 1), date(2026, 4, 1))
        # (150 - 100) * 1.5 = 75.00
        self.assertEqual(montant, Decimal('75.00'))
        self.assertIn('150', description)

    def test_usage_below_franchise_bills_zero_never_negative(self):
        self._reading(date(2026, 3, 5), Decimal('40'))
        montant, description = calculer_ligne_usage_contrat(
            self.contrat, date(2026, 3, 1), date(2026, 4, 1))
        self.assertEqual(montant, Decimal('0.00'))

    def test_no_franchise_bills_full_usage(self):
        self.contrat.franchise_incluse = None
        self.contrat.save(update_fields=['franchise_incluse'])
        self._reading(date(2026, 3, 5), Decimal('60'))
        montant, _ = calculer_ligne_usage_contrat(
            self.contrat, date(2026, 3, 1), date(2026, 4, 1))
        # 60 * 1.5 = 90.00
        self.assertEqual(montant, Decimal('90.00'))

    def test_period_without_reading_omits_line_with_motif(self):
        # Aucun ProductionReading créé pour cette période.
        montant, motif = calculer_ligne_usage_contrat(
            self.contrat, date(2026, 5, 1), date(2026, 6, 1))
        self.assertIsNone(montant)
        self.assertTrue(motif)
        self.assertIn('relevé', motif)

    def test_reading_outside_period_is_excluded(self):
        self._reading(date(2026, 2, 15), Decimal('999'))  # hors période mars
        montant, motif = calculer_ligne_usage_contrat(
            self.contrat, date(2026, 3, 1), date(2026, 4, 1))
        self.assertIsNone(montant)
        self.assertTrue(motif)

    def test_reading_from_other_company_is_excluded(self):
        other_cli = Client.objects.create(
            company=self.other_co, nom='Autre', prenom='Client',
            email='xctr16-other@example.invalid')
        other_inst = Installation.objects.create(
            company=self.other_co, reference='CHT-XCTR16-OTHER',
            client=other_cli)
        self._reading(
            date(2026, 3, 5), Decimal('500'),
            company=self.other_co, installation=other_inst)
        montant, motif = calculer_ligne_usage_contrat(
            self.contrat, date(2026, 3, 1), date(2026, 4, 1))
        self.assertIsNone(montant)

    def test_contract_without_tarif_usage_is_untouched(self):
        self.contrat.tarif_usage = None
        self.contrat.save(update_fields=['tarif_usage'])
        montant, motif = calculer_ligne_usage_contrat(
            self.contrat, date(2026, 3, 1), date(2026, 4, 1))
        self.assertIsNone(montant)
        self.assertIn('tarif', motif.lower())

    def test_contract_without_installation_is_untouched(self):
        contrat_sans_inst = ContratMaintenance.objects.create(
            company=self.co, client=self.cli,
            date_debut=date(2026, 1, 1), actif=True,
            tarif_usage=Decimal('1.5'))
        montant, motif = calculer_ligne_usage_contrat(
            contrat_sans_inst, date(2026, 3, 1), date(2026, 4, 1))
        self.assertIsNone(montant)
        self.assertIn('installation', motif.lower())
