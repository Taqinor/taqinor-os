"""AMOT58 (C-AMOT-024) — le rendement aller-retour de la batterie n'est déduit
qu'UNE fois : flux année 1 de la courbe = économie annuelle imprimée, pour
chaque option et chaque modèle ; en horaire (énergie déjà nette du stockage)
la part batterie du cashflow vaut 0.

Rejoue VB (devis 47 : ``eco_a 7936`` mais flux an 1 de la courbe 7 679,
ratio 0,9676 = 1 − 0,10 × part batterie).

Test-du-test : remettre ``battery_share=_batt_part`` sans la remise à 0
(``rendement_une_fois``) ⇒ ``test_flux_an1_egal_economie_imprimee`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.pricing import calculate_savings_roi


def _roi(une_fois=True, **kw):
    kw.setdefault('battery_kwh', 10.0)
    kw.setdefault('stockage_present', True)
    return calculate_savings_roi(6.0, 60000.0, 95000.0,
                                 rendement_une_fois=une_fois, **kw)


def _flux_an1(cumul, total):
    return cumul[0] + total


class RendementBatterieTests(SimpleTestCase):
    def test_flux_an1_egal_economie_imprimee(self):
        for modele, kw in (('estimation', {}),
                           ('factures', {'conso_annuelle_kwh': 7200,
                                         'utility': 'onee'})):
            with self.subTest(modele=modele):
                roi = _roi(**kw)
                self.assertAlmostEqual(
                    _flux_an1(roi['cashflow_avec'], 95000.0),
                    roi['eco_a_ann'], delta=1.0)
                self.assertAlmostEqual(
                    _flux_an1(roi['cashflow_sans'], 60000.0),
                    roi['eco_s_ann'], delta=1.0)

    def test_regles_d_origine_double_deduction_d_hier(self):
        roi = _roi(une_fois=False)
        self.assertLess(_flux_an1(roi['cashflow_avec'], 95000.0),
                        roi['eco_a_ann'] - 1.0)
