"""APAR4 — ``tariff.monthly_bill_residentiel`` choisit la tranche d'après les
bornes EFFECTIVES du barème : pour toute tolérance éditable, la facture
mensuelle égale celle du chemin devis (``selectors.residential_tranches_for``
→ ``pricing._monthly_bill_from_kwh``) — C-APAR-002."""
import copy
from decimal import Decimal

from django.test import TestCase

from apps.parametres.models_tariff import DEFAULT_RESIDENTIAL_TIERS, TariffSettings
from apps.parametres.selectors import residential_tranches_for
from apps.parametres.tariff import monthly_bill_residentiel
from authentication.models import Company

TOLERANCES = (0, 10, 15, 20)
KWH = (205, 215, 305, 501, 511)


def _bill_devis(company, kwh):
    from apps.ventes.quote_engine.pricing import (
        TrancheTable, _monthly_bill_from_kwh,
    )
    t = residential_tranches_for(company)
    table = TrancheTable(
        t['pairs'], selective_threshold=t['selective_threshold'],
        boundary_tolerance=t['boundary_tolerance'])
    return Decimal(str(_monthly_bill_from_kwh(kwh, table))).quantize(
        Decimal('0.01'))


class ToleranceTarifTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR4 Co', slug='apar4-co')
        self.settings = TariffSettings.get(company=self.company)
        self.settings.residential_tiers = copy.deepcopy(
            DEFAULT_RESIDENTIAL_TIERS)
        self.settings.save()

    def test_tariff_egal_devis_pour_chaque_tolerance(self):
        for tol in TOLERANCES:
            self.settings.tolerance_kwh = tol
            self.settings.save()
            relu = TariffSettings.objects.get(pk=self.settings.pk)
            for kwh in KWH:
                with self.subTest(tol=tol, kwh=kwh):
                    etude = monthly_bill_residentiel(relu, kwh)
                    devis = _bill_devis(self.company, kwh)
                    self.assertLessEqual(
                        abs(etude - devis), Decimal('0.01'),
                        f'tol {tol} / {kwh} kWh : tariff {etude} vs devis {devis}')

    def test_valeurs_tolerance_15_et_10(self):
        for tol in (10, 15):
            self.settings.tolerance_kwh = tol
            self.settings.save()
            relu = TariffSettings.objects.get(pk=self.settings.pk)
            self.assertEqual(
                monthly_bill_residentiel(relu, 205), Decimal('223.73'))
            self.assertEqual(
                monthly_bill_residentiel(relu, 305), Decimal('362.15'))
            self.assertEqual(
                monthly_bill_residentiel(relu, 501), Decimal('692.23'))
