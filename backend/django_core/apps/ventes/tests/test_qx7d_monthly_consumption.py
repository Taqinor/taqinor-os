"""QX7d — la consommation mensuelle affichée n'utilise plus un prix plat figé.

Avant QX7d, ``_monthly_consumption`` divisait la facture par
``constants.KWH_PRICE`` (1,75 MAD/kWh) alors que le chemin ROI valorisait le
kWh via le barème progressif du distributeur (~1,20 en tranche moyenne) : deux
prix contradictoires sur la MÊME proposition. Ce test verrouille l'unification :
la conversion passe désormais par ``pricing.kwh_from_bill`` (mêmes tranches).
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes import public_views
from apps.ventes.quote_engine import pricing


class MonthlyConsumptionQX7dTests(SimpleTestCase):
    def _run(self, bills):
        with mock.patch(
                'apps.crm.selectors.lead_bills_for_devis', return_value=bills):
            return public_views._monthly_consumption(object())

    def test_uses_tranche_aware_conversion_not_flat_175(self):
        bills = {'facture_hiver': 800.0, 'facture_ete': None,
                 'ete_differente': False, 'distributeur': 'onee'}
        out = self._run(bills)
        self.assertEqual(len(out), 12)
        expected = round(
            pricing.kwh_from_bill(800.0, utility='onee').get('kwh_mensuel') or 0)
        self.assertTrue(all(v == expected for v in out))
        # Doit différer du vieux prix plat 1,75 (sinon la régression est revenue).
        self.assertNotEqual(expected, round(800.0 / 1.75))

    def test_summer_bill_applied_to_summer_months(self):
        bills = {'facture_hiver': 900.0, 'facture_ete': 400.0,
                 'ete_differente': True, 'distributeur': 'onee'}
        out = self._run(bills)
        ete = round(pricing.kwh_from_bill(400.0, utility='onee')
                    .get('kwh_mensuel') or 0)
        hiver = round(pricing.kwh_from_bill(900.0, utility='onee')
                      .get('kwh_mensuel') or 0)
        # Index 0=Jan ; été = Mai→Oct (indices 4..9).
        self.assertEqual(out[0], hiver)
        self.assertEqual(out[5], ete)

    def test_no_bills_returns_empty(self):
        self.assertEqual(self._run(None), [])
