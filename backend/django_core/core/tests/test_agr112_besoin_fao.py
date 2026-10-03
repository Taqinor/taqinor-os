# -*- coding: utf-8 -*-
"""AGR112 — besoin FAO-56 corrigé dans le noyau (pur, sans base de données).

Référence AMEE « Olivier 35 » m³/ha/j (bande ± 20 %) : la pointe olivier Tadla
en goutte-à-goutte valait 59,2 avec le Kc plat 0,65 ; le profil mensuel FAO-56
(Table 12, note 24) la ramène dans la bande.
"""

import unittest

from core.pompage import agronomie as g


class OlivierProfilMensuel(unittest.TestCase):

    def test_pointe_olivier_tadla_goutte_dans_la_bande_amee(self):
        r = g.monthly_water_demand(crop="olivier", region="tadla",
                                   surface_ha=1, method="goutte")
        self.assertGreaterEqual(r["peak_m3_ha_day"], 35 * 0.8)
        self.assertLessEqual(r["peak_m3_ha_day"], 35 * 1.2)
        self.assertEqual(r["peak_m3_ha_day"], 41.1)

    def test_profil_pas_070(self):
        kc = g.crop_kc_monthly("olivier")
        self.assertEqual(max(kc), 0.65)
        self.assertNotIn(0.70, kc)
        self.assertEqual(kc[6], 0.45)  # juillet


class CulturesSansProfil(unittest.TestCase):

    def test_maraichage_besoin_null_et_alerte(self):
        r = g.besoin_agronomique([{"culture": "maraichage", "surface_ha": 2,
                                   "methode": "goutte"}], region="tadla")
        self.assertIsNone(r["m3_jour_mois"])
        self.assertEqual([a["code"] for a in r["alertes"]],
                         ["culture_sans_profil"])
        self.assertIn("maraichage", r["alertes"][0]["message"])

    def test_tomate_serre_alerte_sous_abri_sans_facteur(self):
        r = g.besoin_agronomique([{"culture": "tomate-serre", "surface_ha": 1,
                                   "methode": "goutte"}], region="souss-massa")
        self.assertIsNotNone(r["m3_jour_mois"])
        self.assertIn("et0_exterieure_sous_abri",
                      [a["code"] for a in r["alertes"]])
        direct = g.monthly_water_demand(crop="tomate-serre",
                                        region="souss-massa", surface_ha=1,
                                        method="goutte")
        self.assertEqual(r["m3_jour_mois"],
                         [round(v, 1) for v in direct["gross_m3_farm_day"]])


class ParcellesSommees(unittest.TestCase):

    def test_deux_parcelles_sommees_mois_par_mois(self):
        a = g.monthly_water_demand(crop="olivier", region="tadla",
                                   surface_ha=2, method="goutte")
        b = g.monthly_water_demand(crop="agrumes", region="tadla",
                                   surface_ha=1, method="goutte")
        r = g.besoin_agronomique(
            [{"culture": "olivier", "surface_ha": 2, "methode": "goutte"},
             {"culture": "agrumes", "surface_ha": 1, "methode": "goutte"}],
            region="tadla")
        paires = zip(a["gross_m3_farm_day"], b["gross_m3_farm_day"])
        attendu = [round(x + y, 1) for x, y in paires]
        self.assertEqual(r["m3_jour_mois"], attendu)
        self.assertEqual(r["surface_ha"], 3)
        self.assertEqual(len(r["parcelles"]), 2)

    def test_parcelle_sans_profil_omise_les_autres_comptent(self):
        r = g.besoin_agronomique(
            [{"culture": "olivier", "surface_ha": 1, "methode": "goutte"},
             {"culture": "maraichage", "surface_ha": 1}], region="tadla")
        self.assertIsNotNone(r["m3_jour_mois"])
        self.assertEqual(r["surface_ha"], 1)
        self.assertEqual([a["code"] for a in r["alertes"]],
                         ["culture_sans_profil"])


class NatureEtSourceEt0(unittest.TestCase):

    def test_nature_agronomique_plein_et_source_est(self):
        r = g.besoin_agronomique([{"culture": "olivier", "surface_ha": 1}],
                                 region="tadla")
        self.assertEqual(r["nature"], "agronomique_plein")
        self.assertEqual(r["source_et0"], g.source_et0("tadla"))
        # Région inconnue : ET0 médiane, toujours étiquetée « EST. ».
        self.assertEqual(g.source_et0("mars"), "EST.")

    def test_constantes_mortes_supprimees(self):
        for nom in ("CROP_ANNUAL_M3_HA", "CROP_ANNUAL_M3_HA_DEFAUT",
                    "KC_MID_DEFAUT"):
            self.assertFalse(hasattr(g, nom), nom)

    def test_melon_et_gravitaire_conserves(self):
        self.assertEqual(g.CROP_STAGES["melon-pasteque"]["kc_mid"], 1.00)
        self.assertEqual(g.IRRIGATION_EFFICIENCY["gravitaire"], 0.55)

    def test_le_reexport_ventes_pointe_sur_le_noyau(self):
        # Lecture de source : le ré-export n'importe que le noyau (pas de copie).
        import os
        chemin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))),
            "apps", "ventes", "quote_engine", "agricole", "agronomy.py")
        with open(chemin, "r", encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn("from core.pompage.agronomie import", source)
        self.assertNotIn("def monthly_water_demand", source)
