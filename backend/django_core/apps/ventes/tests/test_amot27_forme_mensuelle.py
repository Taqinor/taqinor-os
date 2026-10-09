"""AMOT27 (C-AMOT-027) — l'économie mensuelle (hors modèle horaire) est
répartie par la MÊME forme sourcée que la production
(``constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS``) : ``CLE_SOLAIRE_MENSUELLE`` en
dérive, Σ des mois = annuel au dirham, plus aucun littéral ``0.053, 0.062``
dans ``apps/ventes`` hors ``constants.py``.

``calculate_savings_roi`` réel (modèle estimation). Test-du-test : remettre
le tuple littéral dans ``pricing`` ⇒ ``test_cle_derivee_des_poids_ghi``
échoue.
"""
import pathlib
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine import constants
from apps.ventes.quote_engine.pricing import (
    CLE_SOLAIRE_MENSUELLE, calculate_savings_roi, repartir_mensuel,
)

_VENTES = pathlib.Path(__file__).resolve().parents[1]


class FormeMensuelleTests(SimpleTestCase):
    def test_cle_derivee_des_poids_ghi(self):
        self.assertEqual(list(CLE_SOLAIRE_MENSUELLE),
                         list(constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS))

    def test_estimation_proportionnelle_et_somme_exacte(self):
        roi = calculate_savings_roi(6.0, 60000, 90000, battery_kwh=10)
        self.assertNotEqual(roi['savings_model'], 'horaire')
        for cle_an, cle_m in (('eco_s_ann', 'eco_s_monthly'),
                              ('eco_a_ann', 'eco_a_monthly')):
            annuel, mois = roi[cle_an], roi[cle_m]
            self.assertEqual(sum(mois), round(annuel))
            for v, p in zip(mois, constants.MOROCCO_SOLAR_MONTHLY_WEIGHTS):
                self.assertLessEqual(abs(v - annuel * p), 1)

    def test_repartition_au_dirham(self):
        for total in (0, 1, 12000, 20953, 123456.4):
            self.assertEqual(sum(repartir_mensuel(total)), round(total))

    def test_aucun_litteral_hors_constants(self):
        motif = re.compile(r"0\.053,\s*0\.062")
        fautifs = [str(p.relative_to(_VENTES))
                   for p in _VENTES.rglob('*.py')
                   if p.name != 'constants.py'
                   and p.name != 'test_amot27_forme_mensuelle.py'
                   and motif.search(p.read_text(encoding='utf-8'))]
        self.assertEqual(fautifs, [])
