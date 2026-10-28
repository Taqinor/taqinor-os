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
        from apps.ventes.quote_engine import pricing
        from apps.ventes.quote_engine.pricing import (
            calculate_savings_roi, PRODUCTION_DERATE)
        from apps.ventes.quote_engine.productible import DEFAULT_PRODUCTIBLE
        base = calculate_savings_roi(10.0, 100000, 120000)
        # QRES54 — productible de repli × pertes système (production NETTE).
        # QJR158 (d) — ce repli est LU (plus recopié) : il vaut désormais le
        # repli canonique du dépôt, pas un second chiffre 25 % plus bas.
        self.assertEqual(pricing._DEFAULT_PRODUCTIBLE, DEFAULT_PRODUCTIBLE)
        self.assertEqual(base['prod_kwh'],
                         round(10.0 * pricing._DEFAULT_PRODUCTIBLE
                               * PRODUCTION_DERATE))
        # productible surchargé (au-dessus du repli canonique) → production
        # plus haute que la base
        custom = calculate_savings_roi(10.0, 100000, 120000, productible=1700)
        self.assertEqual(custom['prod_kwh'],
                         round(10.0 * 1700 * PRODUCTION_DERATE))
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

    # ── AMOT64 (D-AMOT-3 = a) — plus de sentinelle 1600 ──────────────────────
    def _prod_attendue(self, data, productible):
        from apps.ventes.quote_engine.pricing import PRODUCTION_DERATE
        return round(data['puissance_kwc'] * productible * PRODUCTION_DERATE)

    def test_amot64_1600_saisi_respecte_et_vide_lit_pvgis(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.productible import productible_for_city
        self._set_profile(productible_kwh_kwc=None)
        vide = build_quote_data(self._devis(reference='DEV-AMOT64-VIDE'))
        pvgis = productible_for_city(vide['client_city'])
        self.assertNotEqual(pvgis, 1600.0)
        self.assertEqual(vide['prod_kwh'], self._prod_attendue(vide, pvgis))
        self._set_profile(productible_kwh_kwc=Decimal('1600.0'))
        saisi = build_quote_data(self._devis(reference='DEV-AMOT64-1600'))
        self.assertEqual(saisi['prod_kwh'], self._prod_attendue(saisi, 1600))

    def test_amot64_migration_ne_bouge_aucun_chiffre_et_se_revert(self):
        import importlib

        from django.apps import apps as registre

        from apps.parametres.models import CompanyProfile
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine.productible import productible_for_city
        mig = importlib.import_module(
            'apps.parametres.migrations.0130_amot64_productible_nullable')
        p = self._set_profile(productible_kwh_kwc=Decimal('1600.0'))
        # Avant la migration, 1600 était la sentinelle ⇒ PVGIS de la ville :
        # c'est ce chiffre-là que le devis doit garder APRÈS la migration.
        mig.sentinelle_vers_null(registre, None)
        p.refresh_from_db()
        self.assertIsNone(p.productible_kwh_kwc)
        data = build_quote_data(self._devis(reference='DEV-AMOT64-MIG'))
        self.assertEqual(data['prod_kwh'], self._prod_attendue(
            data, productible_for_city(data['client_city'])))
        mig.null_vers_sentinelle(registre, None)
        self.assertEqual(
            CompanyProfile.objects.get(pk=p.pk).productible_kwh_kwc,
            Decimal('1600.0'))

    # ── CE2E6 (AMOT64 a) — le productible saisi atteint le moteur HORAIRE ────
    # Emplacement : la série PVGIS est mise à l'échelle DANS le moteur horaire
    # (``horaire.productible_societe``), pas dans ``chiffrer_etude`` : la
    # production ET les économies qui en dérivent bougent ensemble.
    def _bloc_horaire(self, devis):
        from apps.ventes.etude_horaire import etude_horaire_pour_devis
        return etude_horaire_pour_devis(devis, kwc=6.0, data={
            'client_city': 'Casablanca', 'mode_installation': 'residentiel'})

    def _devis_horaire(self, reference, regles=None):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 450W', '10', '1500')], reference=reference,
            etude_params={'conso_kwh_mensuelles': [500] * 12})
        if regles is not None:
            devis.regles_calcul = regles
            devis.save(update_fields=['regles_calcul'])
        return devis

    def test_ce2e6_productible_saisi_respecte_par_le_chemin_horaire(self):
        from apps.parametres.pvgis_profils import productible_mensuel
        from apps.ventes.quote_engine.pricing import (
            PRODUCTION_DERATE, calculate_savings_roi)
        pvgis = sum(productible_mensuel(ville='Casablanca')[0])
        self._set_profile(productible_kwh_kwc=None)
        vide = self._bloc_horaire(self._devis_horaire('DEV-CE2E6-VIDE'))
        self.assertAlmostEqual(vide['annuel']['production_kwh'],
                               6.0 * pvgis * PRODUCTION_DERATE, delta=1)
        self._set_profile(productible_kwh_kwc=Decimal('1650.0'))
        saisi = self._bloc_horaire(self._devis_horaire('DEV-CE2E6-1650'))
        # Même règle que le chemin non horaire : kWc × 1 650 × pertes.
        non_horaire = calculate_savings_roi(6.0, 100000, 120000,
                                            productible=1650)
        self.assertAlmostEqual(saisi['annuel']['production_kwh'],
                               non_horaire['prod_kwh'], delta=1)
        roi = calculate_savings_roi(6.0, 100000, 120000, productible=1650,
                                    etude_horaire=saisi)
        self.assertEqual(roi['savings_model'], 'horaire')
        self.assertEqual(roi['prod_kwh'], non_horaire['prod_kwh'])
        # Les économies suivent la production (aucun chiffre sur l'ancienne).
        self.assertEqual(roi['eco_s_ann'],
                         round(saisi['annuel']['economie_sans_mad']))
        self.assertNotEqual(saisi['annuel']['economie_sans_mad'],
                            vide['annuel']['economie_sans_mad'])
        # Chemin horaire : productible rendu NET (QJR18), = 1 650 × pertes.
        self.assertAlmostEqual(roi['productible'], 1650 * PRODUCTION_DERATE,
                               delta=0.5)

    def test_ce2e6_devis_aux_regles_2_garde_pvgis(self):
        from apps.ventes.horaire.productible_societe import productible_du_devis
        self._set_profile(productible_kwh_kwc=Decimal('1650.0'))
        neuf = self._devis_horaire('DEV-CE2E6-N3')
        ancien = self._devis_horaire('DEV-CE2E6-N2', regles=2)
        self.assertEqual(productible_du_devis(neuf), 1650.0)
        self.assertIsNone(productible_du_devis(ancien))
        self._set_profile(productible_kwh_kwc=None)
        reference = self._bloc_horaire(self._devis_horaire('DEV-CE2E6-REF'))
        self._set_profile(productible_kwh_kwc=Decimal('1650.0'))
        self.assertEqual(self._bloc_horaire(ancien)['annuel'],
                         reference['annuel'])
