"""DC2 — les repères ROI de la société (productible + tarif ONEE) pilotent le ROI.

Avant : productible (1240) et tarif ONEE de repli étaient codés en dur dans
pricing.py → l'écran (simulateur) et le PDF divergeaient dès qu'une société
avait ses propres repères. Ces tests prouvent qu'un productible société modifie
la production/ROI du devis construit, et que le tarif ONEE société sert de repli.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.tests.test_quote_engine import (
    make_company, make_user, make_client, make_devis,
)


class TestDC2CompanyTariff(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, reference='DEV-DC2-0001'):
        # Référence distincte par appel : un même test peut construire deux
        # devis pour la MÊME société (contrainte unique company+reference, et
        # SKU produit dérivé de la référence).
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500'),
            ('Onduleur hybride', '1', '12000'),
        ], reference=reference)

    def _set_profile(self, **fields):
        from apps.parametres.models import CompanyProfile
        p = CompanyProfile.get(company=self.company)
        for k, v in fields.items():
            setattr(p, k, v)
        p.save()
        return p

    def test_pricing_productible_param_changes_production(self):
        from apps.ventes.quote_engine.pricing import (
            calculate_savings_roi, PRODUCTION_DERATE)
        base = calculate_savings_roi(10.0, 100000, 120000)
        # QRES54 — 1240 par défaut × pertes système 14 % (production NETTE)
        self.assertEqual(base['prod_kwh'],
                         round(10.0 * 1240 * PRODUCTION_DERATE))
        # productible surchargé → production différente
        custom = calculate_savings_roi(10.0, 100000, 120000, productible=1600)
        self.assertEqual(custom['prod_kwh'],
                         round(10.0 * 1600 * PRODUCTION_DERATE))
        self.assertGreater(custom['prod_kwh'], base['prod_kwh'])

    def test_pricing_fallback_tarif_used_when_estimated(self):
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        # aucune donnée de conso → repli estimation ; le tarif société s'applique
        roi = calculate_savings_roi(10.0, 100000, 120000,
                                    fallback_tarif_kwh=2.50)
        self.assertTrue(roi['savings_estimated'])
        self.assertEqual(roi['tarif_kwh'], 2.50)

    def test_company_productible_changes_built_quote_roi(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        self._set_profile(productible_kwh_kwc=Decimal('1240.0'))
        data_low = build_quote_data(self._devis(reference='DEV-DC2-LOW'))
        self._set_profile(productible_kwh_kwc=Decimal('1600.0'))
        data_high = build_quote_data(self._devis(reference='DEV-DC2-HIGH'))
        # Un productible plus élevé produit plus de kWh et donc plus d'économies.
        self.assertGreater(data_high['prod_kwh'], data_low['prod_kwh'])
        self.assertGreater(data_high['eco_s_ann'], data_low['eco_s_ann'])
