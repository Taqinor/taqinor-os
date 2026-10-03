# -*- coding: utf-8 -*-
"""AGR114 — production d'eau heure par heure (noyau pur, sans base).

Courbe OSP 30/8 du catalogue semé (``seed_catalogue.py`` : débits 0-39 m³/h,
HMT 91 → 34 m, 7,5 kW). Les profils horaires sont SYNTHÉTIQUES (forme ciel
clair du noyau) : seul le comportement relatif est vérifié.
"""

import unittest

from core.pompage import agronomie
from core.pompage.volumes import (
    _CLEARSKY_HOURLY_SHAPE, ESTIMATION_SIMILITUDE, mois_critique,
    production_mensuelle,
)

OSP_30_8 = {"debits_m3h": [0, 12, 24, 30, 36, 39],
            "hmt_m": [91, 85, 70, 60, 43, 34]}

PIC = max(_CLEARSKY_HOURLY_SHAPE)
#: Irradiance de pic par mois (W/m²) — synthétique, hiver plus faible.
PICS = (650, 720, 820, 900, 950, 980, 990, 960, 880, 780, 680, 630)
PROFILS = tuple(tuple(f / PIC * g for f in _CLEARSKY_HOURLY_SHAPE)
                for g in PICS)

BASE = dict(kwc=10.5, profils_horaires=PROFILS, courbe_pompe=OSP_30_8,
            p_plaque_kw=7.5)


class ProductionCourbe(unittest.TestCase):

    def test_hmt_80_moins_d_heures_equivalentes_qu_a_40(self):
        haut = production_mensuelle(hmt_m=80, **BASE)
        bas = production_mensuelle(hmt_m=40, **BASE)
        self.assertEqual(haut["mode"], "courbe")
        for mois in range(12):
            self.assertLess(haut["heures_equivalentes_mois"][mois],
                            bas["heures_equivalentes_mois"][mois])
        self.assertIn(ESTIMATION_SIMILITUDE, haut["etiquettes"])

    def test_zero_sous_le_point_d_arret(self):
        # HMT au-delà de l'arrêt de la courbe (91 m) : la pompe ne débite pas.
        r = production_mensuelle(hmt_m=95, **BASE)
        self.assertEqual(r["m3_jour_mois"], [0.0] * 12)
        self.assertEqual(r["heures_equivalentes_mois"], [None] * 12)
        r = production_mensuelle(hmt_m=90, **dict(BASE, kwc=0.5))
        self.assertEqual(r["m3_jour_mois"], [0.0] * 12)

    def test_ete_produit_plus_que_l_hiver(self):
        r = production_mensuelle(hmt_m=60, **BASE)
        self.assertGreater(r["m3_jour_mois"][6], r["m3_jour_mois"][11])
        self.assertEqual(r["source_irradiation"], "pvgis")

    def test_pertes_pvgis_jamais_derate_supplementaire(self):
        sans = production_mensuelle(hmt_m=60, **BASE)
        avec_salissure = production_mensuelle(hmt_m=60, salissure_pct=5, **BASE)
        self.assertLessEqual(avec_salissure["m3_jour_mois"][0],
                             sans["m3_jour_mois"][0])
        # Sans réglage ni fiche MPPT, P = kWc × G / 1000 tel quel.
        self.assertEqual(production_mensuelle(hmt_m=60, salissure_pct=None,
                                              rendement_mppt=None, **BASE),
                         sans)

    def test_coordonnees_et_reponse_pvgis_rendues_pour_etre_figees(self):
        coords = {"lat": 30.47, "lon": -8.88, "fige_le": "2026-10-02"}
        r = production_mensuelle(hmt_m=60, coordonnees=coords,
                                 reponse_pvgis={"E_m": [1] * 12}, **BASE)
        self.assertEqual(r["coordonnees_figees"], coords)
        self.assertEqual(r["reponse_pvgis"], {"E_m": [1] * 12})


class CasDegrades(unittest.TestCase):

    def test_pompe_sans_courbe_production_null(self):
        r = production_mensuelle(hmt_m=60, **dict(BASE, courbe_pompe=None))
        self.assertIsNone(r["m3_jour_mois"])
        self.assertIn("sans courbe", r["motif"])

    def test_sans_profil_repli_plat_etiquete(self):
        r = production_mensuelle(hmt_m=60, agricole_pump_hours=7,
                                 **dict(BASE, profils_horaires=None))
        self.assertEqual(r["mode"], "repli_plat")
        self.assertEqual(r["source_irradiation"], "repli")
        self.assertEqual(r["m3_jour_mois"], [round(30.0 * 7, 1)] * 12)
        self.assertTrue(any("repli" in e for e in r["etiquettes"]))

    def test_sans_profil_ni_heures_rien_d_invente(self):
        r = production_mensuelle(hmt_m=60, **dict(BASE, profils_horaires=None))
        self.assertIsNone(r["m3_jour_mois"])
        self.assertIsNotNone(r["motif"])

    def test_pompe_existante_debit_declare(self):
        r = production_mensuelle(hmt_m=60, debit_declare_m3h=10,
                                 **dict(BASE, courbe_pompe=None))
        self.assertEqual(r["mode"], "debit_declare")
        self.assertTrue(any("débit déclaré" in e for e in r["etiquettes"]))
        attendu = round(sum(10 * min(1.0, 10.5 * g / 1000 / 7.5)
                            for g in PROFILS[0]), 1)
        self.assertEqual(r["m3_jour_mois"][0], attendu)


class MoisCritique(unittest.TestCase):

    def test_argmax_sur_un_besoin_d_hiver_fraise(self):
        besoin = agronomie.besoin_agronomique(
            [{"culture": "fraise", "surface_ha": 2, "methode": "goutte"}],
            region="souss-massa")["m3_jour_mois"]
        r = production_mensuelle(hmt_m=60, besoin_m3_jour_mois=besoin, **BASE)
        prod = r["m3_jour_mois"]
        rapports = [(besoin[m] / prod[m]) if besoin[m] > 0 else -1
                    for m in range(12)]
        attendu = rapports.index(max(rapports)) + 1
        self.assertEqual(r["mois_critique"], attendu)
        # Besoin d'hiver : aucun besoin de fraise en juillet, mois où la
        # production est maximale — le critique n'est jamais ce mois-là.
        self.assertEqual(besoin[6], 0)
        self.assertNotEqual(r["mois_critique"], 7)

    def test_production_nulle_critique_d_office(self):
        self.assertEqual(mois_critique([1] * 12, [5] * 11 + [0]), 12)

    def test_sans_besoin_none(self):
        self.assertIsNone(mois_critique(None, [1] * 12))
