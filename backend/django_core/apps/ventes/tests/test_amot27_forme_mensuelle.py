"""AMOT27 (C-AMOT-027) — l'économie mensuelle (hors modèle horaire) est
répartie par la MÊME forme sourcée que la production
(``constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS``) : ``CLE_SOLAIRE_MENSUELLE``
dérivée des poids GHI, Σ = annuel au dirham, plus aucun littéral
``0.053, 0.062`` dans ``apps/ventes`` hors ``constants.py``.

Rejoue VB (écarts ``[-0.9, 0.6, -2.3, …]`` % entre la clé fixe et la forme
GHI ; devis 176 ``eco_s_monthly [607, 710, 950, …]``).

Test-du-test : remettre le tuple littéral dans ``pricing`` ⇒ rouge.
"""
import pathlib
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import pricing
from apps.ventes.quote_engine.constants import (
    CLE_SOLAIRE_MENSUELLE_HISTORIQUE, MOROCCO_SOLAR_MONTHLY_WEIGHTS)

VENTES = pathlib.Path(pricing.__file__).resolve().parents[1]


class FormeMensuelleTests(SimpleTestCase):
    def test_cle_derivee_des_poids_ghi(self):
        self.assertEqual(pricing.CLE_SOLAIRE_MENSUELLE,
                         tuple(MOROCCO_SOLAR_MONTHLY_WEIGHTS))

    def test_estimation_et_factures_proportionnelles(self):
        for kw in ({}, {'conso_annuelle_kwh': 7200, 'utility': 'onee'}):
            with self.subTest(kw=kw):
                roi = pricing.calculate_savings_roi(
                    6.0, 60000.0, 95000.0, forme_mensuelle_ghi=True, **kw)
                for cle_m, cle_a in (('eco_s_monthly', 'eco_s_ann'),
                                     ('eco_a_monthly', 'eco_a_ann')):
                    mois = roi[cle_m]
                    self.assertEqual(sum(mois), round(roi[cle_a]))
                    for m, poids in zip(mois, MOROCCO_SOLAR_MONTHLY_WEIGHTS):
                        self.assertLessEqual(
                            abs(m - roi[cle_a] * poids), 6.0)

    def test_regles_d_origine_cle_historique(self):
        roi = pricing.calculate_savings_roi(6.0, 60000.0, 95000.0)
        self.assertEqual(
            roi['eco_s_monthly'],
            [round(roi['eco_s_ann'] * f)
             for f in CLE_SOLAIRE_MENSUELLE_HISTORIQUE])

    def test_aucun_litteral_hors_constants(self):
        motif = re.compile(r'0\.053,\s*0\.062')
        fautifs = [str(p.relative_to(VENTES)) for p in VENTES.rglob('*.py')
                   if p.name != 'constants.py'
                   and p.name != pathlib.Path(__file__).name
                   and motif.search(p.read_text(encoding='utf-8'))]
        self.assertEqual(fautifs, [])
