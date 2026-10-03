# -*- coding: utf-8 -*-
"""AGR133 — cas de référence EXTERNES en non-régression du noyau de pompage.

Les tests portent sur les FONCTIONS du noyau (énergie → kWc, contrôle de
conception, besoin agronomique), jamais sur la sélection de pompe : ces cas
sont sous la gamme à courbe du catalogue. Chaque cas cite sa source.

Rendement : le kWc de départ AGR115 vaut E / (η × E_d). Les deux références
de dimensionnement (AMEE, SPIS) ne publient pas leur η ; elles sont tenues à
± 20 % avec la borne BASSE de la plage AMEE citée par la table AGR110
(``rendement_groupe`` : « plage AMEE 0,35-0,55 »), lue dans la table — jamais
recopiée ici. Avec la valeur par défaut « EST. » de la table (0,5), elles NE
sont PAS tenues (kWc sous-estimé de 17 à 37 %) : cas rouge gardé en
``expectedFailure`` tant que le réglage n'est pas tranché.
"""

import re
import unittest

from core.pompage.agronomie import monthly_water_demand
from core.pompage.champ import kwc_depart
from core.pompage.conception import controle_conception
from core.pompage.hypotheses import hypothese, valeur

BANDE = 0.20

#: Guide PSIA de l'AMEE (PDF créé le 14/01/2019 ; lien amee.ma en 404 le
#: 02/10/2026) — exemple FOURNISSEUR « Source : Sewt Solar », jamais imprimé
#: au client. 72 m³/j, irradiation 5,9 kWh/m²/j (Errachidia) ; HMT → kWc.
AMEE_VOLUME_M3_J = 72
AMEE_IRRADIATION = 5.9
AMEE_TABLE = ((30, 2.75), (55, 4.4), (70, 7.42), (120, 10.45), (145, 12.1))

#: SPIS Toolbox (GIZ/FAO v1.0, janvier 2017) : 30 m³/j, 50 m, 5 kWh/m²/j →
#: 2 400 Wc.
SPIS = {"volume": 30, "hmt": 50, "irradiation": 5, "kwc": 2.4}

#: Water Mission 2019 : 15 100 L produits pour 13 120 L demandés.
WATER_MISSION = {"produit_m3": 15.1, "demande_m3": 13.12}

#: Olivier à Tadla en goutte-à-goutte : pointe 35 ± 20 % m³/ha/j.
OLIVIER_TADLA_POINTE = 35


def _eta_amee_bas():
    """Borne basse de la plage AMEE citée par la table AGR110."""
    source = hypothese("rendement_groupe").source
    bas, _haut = re.search(r"(\d,\d+)-(\d,\d+)", source).groups()
    return float(bas.replace(",", "."))


def _dans_bande(test, calcule, reference):
    test.assertIsNotNone(calcule)
    test.assertLessEqual(abs(calcule / reference - 1), BANDE,
                         "%.2f vs %.2f" % (calcule, reference))


class EnergieVersKwc(unittest.TestCase):

    def test_amee_guide_psia_72_m3_j(self):
        eta = _eta_amee_bas()
        self.assertEqual(eta, 0.35)
        for hmt, reference in AMEE_TABLE:
            with self.subTest(hmt=hmt):
                _dans_bande(self, kwc_depart(AMEE_VOLUME_M3_J, hmt,
                                             AMEE_IRRADIATION, eta),
                            reference)

    def test_spis_giz_fao_2017(self):
        _dans_bande(self, kwc_depart(SPIS["volume"], SPIS["hmt"],
                                     SPIS["irradiation"], _eta_amee_bas()),
                    SPIS["kwc"])

    @unittest.expectedFailure
    def test_references_tenues_avec_le_rendement_par_defaut(self):
        """ROUGE : avec ``rendement_groupe`` = 0,5 « EST. » (défaut de la
        table AGR110), AMEE et SPIS sortent de la bande ± 20 %."""
        eta = valeur("rendement_groupe")
        for hmt, reference in AMEE_TABLE:
            _dans_bande(self, kwc_depart(AMEE_VOLUME_M3_J, hmt,
                                         AMEE_IRRADIATION, eta), reference)
        _dans_bande(self, kwc_depart(SPIS["volume"], SPIS["hmt"],
                                     SPIS["irradiation"], eta), SPIS["kwc"])


class ControleConception(unittest.TestCase):

    def test_water_mission_2019_dans_la_tolerance(self):
        res = controle_conception([WATER_MISSION["demande_m3"]] * 12,
                                  [WATER_MISSION["produit_m3"]] * 12, 1)
        self.assertEqual(res["statut"], "conforme")
        self.assertEqual(res["couverture_mois_critique_pct"], 115)


class BesoinAgronomique(unittest.TestCase):

    def test_olivier_tadla_goutte_a_goutte(self):
        res = monthly_water_demand("olivier", "tadla", 1, "goutte")
        _dans_bande(self, res["peak_m3_ha_day"], OLIVIER_TADLA_POINTE)


if __name__ == "__main__":
    unittest.main()
