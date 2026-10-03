# -*- coding: utf-8 -*-
"""AGR116 — débit de conception, plafonds et alertes (noyau pur, sans base)."""

import unittest

from core.pompage.conception import (
    besoin_retenu, conception, controle_conception, heures_pic,
)
from core.pompage.volumes import _CLEARSKY_HOURLY_SHAPE

PIC = max(_CLEARSKY_HOURLY_SHAPE)
PROFILS = tuple(tuple(f / PIC * 900 for f in _CLEARSKY_HOURLY_SHAPE)
                for _ in range(12))
H_PIC = heures_pic(PROFILS[0])

FAO_300 = {"m3_jour_mois": [300.0] * 12, "source_et0": "EST.",
           "nature": "agronomique_plein"}


def _codes(resultat):
    return [a["code"] for a in resultat["alertes"]]


class BesoinRetenu(unittest.TestCase):

    def test_declare_120_et_fao_300_conception_sur_120_les_deux_servis(self):
        besoin = besoin_retenu(volume_declare_m3_jour=120,
                               besoin_agronomique=FAO_300)
        self.assertEqual(besoin["nature"], "declare")
        self.assertEqual(besoin["m3_jour_mois"], [120.0] * 12)
        self.assertEqual(besoin["autre_besoin"]["nature"], "agronomique_plein")
        self.assertEqual(besoin["autre_besoin"]["ecart_pointe_m3_jour"], 180.0)
        r = conception(besoin=besoin, profils_horaires=PROFILS,
                       debit_exploitation_m3h=100, niveau_eau_m=30)
        self.assertAlmostEqual(r["conception"]["debit_conception_m3h"],
                               round(120 / H_PIC, 1))

    def test_jamais_le_maximum(self):
        besoin = besoin_retenu(volume_declare_m3_jour=400,
                               besoin_agronomique=FAO_300)
        self.assertEqual(besoin["m3_jour_mois"], [400.0] * 12)

    def test_besoin_actuel_debit_par_heures_actuelles(self):
        besoin = besoin_retenu(debit_actuel_m3h=10, heures_actuelles=6)
        self.assertEqual(besoin["m3_jour_mois"], [60.0] * 12)
        self.assertIn("heures actuelles", besoin["provenance"]["detail"])

    def test_repli_fao_nomme_agronomique_plein(self):
        besoin = besoin_retenu(besoin_agronomique=FAO_300)
        self.assertEqual(besoin["nature"], "agronomique_plein")
        self.assertEqual(besoin["source_et0"], "EST.")

    def test_mois_d_irrigation_declares(self):
        besoin = besoin_retenu(volume_declare_m3_jour=50,
                               mois_irrigation=[5, 6, 7])
        self.assertEqual(besoin["m3_jour_mois"][4:7], [50.0] * 3)
        self.assertEqual(besoin["m3_jour_mois"][0], 0.0)


class Plafonds(unittest.TestCase):

    def test_forage_20_pour_un_besoin_de_32(self):
        volume = 32 * H_PIC
        r = conception(besoin=besoin_retenu(volume_declare_m3_jour=volume),
                       profils_horaires=PROFILS, debit_exploitation_m3h=20,
                       niveau_eau_m=30)
        self.assertEqual(r["conception"]["debit_conception_m3h"], 20)
        self.assertTrue(r["conception"]["plafonds"]["atteint"])
        self.assertIn("plafond_forage", _codes(r))

    def test_part_du_reglage_appliquee_si_saisie(self):
        r = conception(besoin=besoin_retenu(volume_declare_m3_jour=32 * H_PIC),
                       profils_horaires=PROFILS, debit_exploitation_m3h=20,
                       part_reglage_pct=80, niveau_eau_m=30)
        self.assertEqual(r["conception"]["plafonds"]["plafond_retenu_m3h"], 16)

    def test_volume_annuel_superieur_a_l_autorise(self):
        r = conception(besoin=besoin_retenu(volume_declare_m3_jour=100),
                       profils_horaires=PROFILS, debit_exploitation_m3h=50,
                       niveau_eau_m=30, volume_autorise_m3_an=10000)
        self.assertIn("volume_autorise_depasse", _codes(r))


class Alertes(unittest.TestCase):

    def test_pompe_actuelle_6cv_80m_80m3h_incoherente(self):
        r = conception(besoin=besoin_retenu(debit_actuel_m3h=80,
                                            heures_actuelles=6),
                       profils_horaires=PROFILS, debit_exploitation_m3h=100,
                       niveau_eau_m=60, hmt_m=80, debit_actuel_m3h=80,
                       pompe_actuelle_kw=6 * 0.7355)
        self.assertIn("debit_actuel_incoherent", _codes(r))
        alerte = [a for a in r["alertes"]
                  if a["code"] == "debit_actuel_incoherent"][0]
        self.assertEqual(alerte["champ"], "debit_actuel_m3h")

    def test_pompe_actuelle_coherente_sans_alerte(self):
        r = conception(besoin=besoin_retenu(debit_actuel_m3h=5,
                                            heures_actuelles=6),
                       profils_horaires=PROFILS, debit_exploitation_m3h=100,
                       niveau_eau_m=60, hmt_m=80, debit_actuel_m3h=5,
                       pompe_actuelle_kw=6 * 0.7355)
        self.assertNotIn("debit_actuel_incoherent", _codes(r))

    def test_niveau_inconnu_releve_requis_d_agr_4(self):
        r = conception(besoin=besoin_retenu(volume_declare_m3_jour=100),
                       profils_horaires=PROFILS, debit_exploitation_m3h=50)
        self.assertIn("releve_point_eau_requis", _codes(r))

    def test_couverture_90_insuffisante_et_130_surdimensionnement(self):
        besoin = besoin_retenu(volume_declare_m3_jour=100)
        for prod, statut in ((90, "couverture_insuffisante"),
                             (130, "surdimensionnement"),
                             (100, "conforme")):
            r = conception(besoin=besoin, profils_horaires=PROFILS,
                           debit_exploitation_m3h=50, niveau_eau_m=30,
                           production_m3_jour_mois=[prod] * 12)
            self.assertEqual(r["controle_conception"]["statut"], statut)
            if statut != "conforme":
                self.assertIn(statut, _codes(r))

    def test_controle_sans_production_non_verifiable(self):
        self.assertEqual(controle_conception([100] * 12, None, 1)["statut"],
                         "non_verifiable")

    def test_autonomie_reservoir_declare_seulement(self):
        besoin = besoin_retenu(volume_declare_m3_jour=100)
        r = conception(besoin=besoin, profils_horaires=PROFILS)
        self.assertIsNone(r["autonomie_reservoir_jours"]["valeur"])
        r = conception(besoin=besoin, profils_horaires=PROFILS,
                       volume_reservoir_m3=250)
        self.assertEqual(r["autonomie_reservoir_jours"]["valeur"], 2.5)

    def test_sans_profil_ni_reglage_rien_d_invente(self):
        r = conception(besoin=besoin_retenu(volume_declare_m3_jour=100))
        self.assertIsNone(r["conception"]["debit_conception_m3h"])
        self.assertIn("heures_pic_inconnues", _codes(r))
