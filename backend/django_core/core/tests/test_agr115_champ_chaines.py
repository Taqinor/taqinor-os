# -*- coding: utf-8 -*-
"""AGR115 — champ PV sur le mois critique, chaînes contre la fenêtre du
variateur, variateur sur la PLAQUE (noyau pur, sans base).

Données ILLUSTRATIVES : noms et kW des variateurs recopiés du seed
(``seed_catalogue.py`` VEICHI) ; la fiche « 250-780 V » est celle du constat
C5-02 ; le panneau 710 Wc a un Vmp de 40,4 V (6 panneaux ≈ 242 V, C5-02). Les
profils horaires sont SYNTHÉTIQUES (forme ciel clair du noyau).
"""

import unittest

from core.pompage.champ import (
    MENTION_TEMPERATURES_REPLI, choisir_variateur, dimensionner_champ,
    e_d_depuis_profils, kwc_depart,
)
from core.pompage.volumes import _CLEARSKY_HOURLY_SHAPE

PIC = max(_CLEARSKY_HOURLY_SHAPE)
PICS = (650, 720, 820, 900, 950, 980, 990, 960, 880, 780, 680, 630)
PROFILS = tuple(tuple(f / PIC * g for f in _CLEARSKY_HOURLY_SHAPE)
                for g in PICS)

PANNEAU = {"id": 3, "nom": "Panneau 710W", "pmax_wc": 710, "vmp_v": 40.4,
           "voc_v": 48.6, "isc_a": 18.6, "imp_a": 17.6,
           "temp_coeff_voc_pct_c": -0.25, "temp_coeff_pmax_pct_c": -0.29}

FICHE_250_780 = {"type_fiche": "variateur_pompage", "ond_mppt_v_min": 250,
                 "ond_mppt_v_max": 780, "ond_v_max_abs": 800,
                 "ond_i_max_mppt_a": 20, "ond_phases": None,
                 "ond_v_demarrage_v": None}

OSP_30_8 = {"debits_m3h": [0, 12, 24, 30, 36, 39],
            "hmt_m": [91, 85, 70, 60, 43, 34]}


def _var(id_, kw, tension, fiche=None, prix=True):
    return {"id": id_, "nom": "VARIATEUR VEICHI SI23 %sKW %sV" % (kw, tension),
            "role_pompage": "variateur_pompage", "pompe_kw": str(kw),
            "tension_v": tension, "fiche": fiche, "prix_connu": prix}


CATALOGUE = [
    {"id": 1, "nom": "VARIATEUR VEICHI SI22 2.2KW 220V",
     "role_pompage": "variateur_pompage", "pompe_kw": "2.2", "tension_v": 220,
     "fiche": None, "prix_connu": True, "prix_vente": 1580},
    {"id": 2, "nom": "VARIATEUR VEICHI SI23 2.2KW 220V",
     "role_pompage": "variateur_pompage", "pompe_kw": "2.2", "tension_v": 220,
     "fiche": None, "prix_connu": True, "prix_vente": 2530},
    _var(3, 2.2, 380),
    _var(4, 4, 380, fiche=FICHE_250_780),
    _var(5, 5.5, 380),
    _var(6, 7.5, 380),
    {"id": 7, "nom": "AFFICHEUR VARIATEUR SI22", "role_pompage":
     "afficheur_variateur", "pompe_kw": None, "prix_connu": True},
]


class ChoixVariateur(unittest.TestCase):

    def test_pompe_3cv_mono_kw_plaque_2_2_donne_variateur_220v_2_2(self):
        res = choisir_variateur(CATALOGUE, kw_plaque="2.2", cv="3",
                                alimentation="mono")
        self.assertIsNotNone(res["variateur"])
        self.assertEqual(res["variateur"]["pompe_kw"], "2.2")
        self.assertEqual(res["variateur"]["tension_v"], 220)
        self.assertEqual(res["source_kw"], "plaque")
        self.assertFalse([a for a in res["alertes"]
                          if a["code"] == "aucun_variateur"])

    def test_pompe_5_5cv_avec_kw_plaque_4_donne_variateur_4kw(self):
        res = choisir_variateur(CATALOGUE, kw_plaque="4", cv="5.5",
                                alimentation="tri")
        self.assertEqual(res["variateur"]["id"], 4)
        self.assertEqual(res["kw_requis"], 4.0)

    def test_cv_seul_alerte_kw_plaque_a_relever_et_jamais_aucun(self):
        res = choisir_variateur(CATALOGUE, cv="3", alimentation="mono")
        codes = [a["code"] for a in res["alertes"]]
        self.assertIn("kw_plaque_a_relever", codes)
        # 3 CV × 0,7355 = 2,21 kW > 2,2 kW : l'alerte nomme la limite.
        self.assertIn("aucun_variateur", codes)
        self.assertIn("220 V", res["motif"])

    def test_phases_publiees_incompatibles_exclues(self):
        fiche_tri = dict(FICHE_250_780, ond_phases=3)
        cat = [_var(10, 2.2, 220, fiche=fiche_tri)]
        res = choisir_variateur(cat, kw_plaque=2.2, alimentation="mono")
        self.assertIsNone(res["variateur"])

    def test_courant_sortie_insuffisant_exclu(self):
        fiche = dict(FICHE_250_780, var_i_sortie_nominal_a=9)
        cat = [_var(11, 4, 380, fiche=fiche), _var(12, 5.5, 380)]
        res = choisir_variateur(cat, kw_plaque=4, alimentation="tri",
                                courant_nominal_a=10)
        self.assertEqual(res["variateur"]["id"], 12)

    def test_sans_prix_jamais_retenu(self):
        cat = [_var(13, 4, 380, prix=False)]
        res = choisir_variateur(cat, kw_plaque=4, alimentation="tri")
        self.assertIsNone(res["variateur"])
        self.assertEqual(res["sans_prix"], [cat[0]["nom"]])


class EnergieKwc(unittest.TestCase):

    def test_kwc_depart_formule(self):
        # E = 2,725 × 72 × 30 / 1000 = 5,886 kWh/j ; η 0,5 ; E_d 5,9.
        self.assertAlmostEqual(kwc_depart(72, 30, 5.9, 0.5),
                               5.886 / (0.5 * 5.9), places=6)
        self.assertIsNone(kwc_depart(None, 30, 5.9, 0.5))

    def test_e_d_depuis_profils(self):
        e_d = e_d_depuis_profils(PROFILS)
        self.assertEqual(len(e_d), 12)
        self.assertLess(e_d[11], e_d[6])


class Champ(unittest.TestCase):

    def test_4cv_tri_fenetre_250_780_releve_au_minimum_de_chaine(self):
        choix = choisir_variateur(CATALOGUE, kw_plaque=3, cv=4,
                                  alimentation="tri")
        self.assertEqual(choix["variateur"]["id"], 4)
        res = dimensionner_champ(
            besoin_m3_jour_mois=[20.0] * 12, hmt_m=40, panneau=PANNEAU,
            variateurs_candidats=choix["candidats"], p_plaque_kw=3,
            profils_horaires=PROFILS)
        # Énergie : quelques panneaux seulement ; Vmp à 70 °C ≈ 35,1 V ⇒
        # ⌈250 / 35,1⌉ = 8 panneaux minimum en série.
        self.assertLess(res["kwc_depart"] * 1000 / 710, 8)
        self.assertEqual(res["nb_panneaux"], 8)
        self.assertEqual(res["chaines"]["serie"], 8)
        self.assertTrue(res["chaines"]["verifiable"])
        self.assertIn("champ_impose_fenetre",
                      [a["code"] for a in res["alertes"]])
        # Températures TMY absentes : replis du noyau électrique MENTIONNÉS.
        self.assertEqual(res["chaines"]["temperatures"]["mention"],
                         MENTION_TEMPERATURES_REPLI)

    def test_variateur_sans_fiche_alerte_nommee(self):
        cat = [_var(20, 7.5, 380)]
        res = dimensionner_champ(
            besoin_m3_jour_mois=[135.0] * 12, hmt_m=58.7, panneau=PANNEAU,
            variateurs_candidats=cat, pompe={"courbe_pompe": OSP_30_8},
            p_plaque_kw=7.5, profils_horaires=PROFILS)
        self.assertFalse(res["chaines"]["verifiable"])
        self.assertIn("non vérifiable", res["chaines"]["motif"])
        alerte = [a for a in res["alertes"]
                  if a["code"] == "chaine_non_verifiable"]
        self.assertTrue(alerte)
        self.assertIn(cat[0]["nom"], alerte[0]["message"])
        self.assertIsNotNone(res["nb_panneaux"])

    def test_plus_petit_nombre_qui_couvre_le_mois_critique(self):
        params = dict(besoin_m3_jour_mois=[135.0] * 12, hmt_m=58.7,
                      panneau=PANNEAU, variateurs_candidats=[_var(21, 7.5, 380)],
                      pompe={"courbe_pompe": OSP_30_8}, p_plaque_kw=7.5,
                      profils_horaires=PROFILS)
        res = dimensionner_champ(**params)
        mois = res["mois_critique"]
        self.assertEqual(mois, 12)  # décembre : irradiation la plus faible
        prod = res["production"]["m3_jour_mois"]
        self.assertGreaterEqual(prod[mois - 1], 135.0)
        # Un panneau de moins ne couvre plus.
        from core.pompage.volumes import production_mensuelle
        moins = production_mensuelle(
            kwc=(res["nb_panneaux"] - 1) * 0.71, profils_horaires=PROFILS,
            courbe_pompe=OSP_30_8, hmt_m=58.7, p_plaque_kw=7.5)
        self.assertLess(moins["m3_jour_mois"][mois - 1], 135.0)

    def test_chaine_trop_longue_paralleles_si_courant_le_permet(self):
        fiche = dict(FICHE_250_780, ond_mppt_v_max=400, ond_v_max_abs=450,
                     ond_mppt_v_min=150, ond_i_max_mppt_a=40)
        res = dimensionner_champ(
            besoin_m3_jour_mois=[135.0] * 12, hmt_m=58.7, panneau=PANNEAU,
            variateurs_candidats=[_var(22, 7.5, 380, fiche=fiche)],
            pompe={"courbe_pompe": OSP_30_8}, p_plaque_kw=7.5,
            profils_horaires=PROFILS)
        ch = res["chaines"]
        self.assertGreater(ch["paralleles"], 1)
        self.assertEqual(ch["serie"] * ch["paralleles"], res["nb_panneaux"])

    def test_courant_insuffisant_variateur_suivant(self):
        fiche_petit = dict(FICHE_250_780, ond_mppt_v_max=400,
                           ond_v_max_abs=450, ond_mppt_v_min=150,
                           ond_i_max_mppt_a=20)
        fiche_gros = dict(fiche_petit, ond_mppt_v_max=780, ond_v_max_abs=800)
        candidats = [_var(23, 7.5, 380, fiche=fiche_petit),
                     _var(24, 11, 380, fiche=fiche_gros)]
        res = dimensionner_champ(
            besoin_m3_jour_mois=[135.0] * 12, hmt_m=58.7, panneau=PANNEAU,
            variateurs_candidats=candidats, pompe={"courbe_pompe": OSP_30_8},
            p_plaque_kw=7.5, profils_horaires=PROFILS)
        self.assertEqual(res["variateur"]["id"], 24)
        self.assertIn("variateur_suivant", [a["code"] for a in res["alertes"]])

    def test_ratio_hors_bande_alerte_seule(self):
        res = dimensionner_champ(
            besoin_m3_jour_mois=[20.0] * 12, hmt_m=40, panneau=PANNEAU,
            variateurs_candidats=[_var(25, 7.5, 380)], p_plaque_kw=7.5,
            profils_horaires=PROFILS)
        self.assertIsNotNone(res["nb_panneaux"])
        self.assertIn("ratio_champ_pompe", [a["code"] for a in res["alertes"]])

    def test_temperatures_tmy_du_site_utilisees(self):
        choix = choisir_variateur(CATALOGUE, kw_plaque=3, alimentation="tri")
        res = dimensionner_champ(
            besoin_m3_jour_mois=[20.0] * 12, hmt_m=40, panneau=PANNEAU,
            variateurs_candidats=choix["candidats"], p_plaque_kw=3,
            profils_horaires=PROFILS,
            temperatures={"froid_c": 2, "chaud_c": 60, "source": "tmy_site"})
        temp = res["chaines"]["temperatures"]
        self.assertEqual((temp["froid_c"], temp["chaud_c"]), (2, 60))
        self.assertIsNone(temp["mention"])

    def test_panneau_sans_fiche_jamais_muet(self):
        res = dimensionner_champ(
            besoin_m3_jour_mois=[20.0] * 12, hmt_m=40,
            panneau={"pmax_wc": 710}, profils_horaires=PROFILS)
        self.assertIsNone(res["nb_panneaux"])
        self.assertIn("panneau_sans_fiche", [a["code"] for a in res["alertes"]])


if __name__ == "__main__":
    unittest.main()
