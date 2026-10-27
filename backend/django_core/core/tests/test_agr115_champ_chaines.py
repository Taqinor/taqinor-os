# -*- coding: utf-8 -*-
"""AGR115 — champ PV sur le mois critique, chaînes contre la fenêtre du
variateur, variateur sur la PLAQUE (noyau pur, sans base).

Données ILLUSTRATIVES : noms et kW des variateurs recopiés du seed
(``seed_catalogue.py`` VEICHI) ; la fiche « 250-780 V » est celle du constat
C5-02 ; le panneau 710 Wc a un Vmp de 40,4 V (6 panneaux ≈ 242 V, C5-02). Les
profils horaires sont SYNTHÉTIQUES (forme ciel clair du noyau).
"""

import math
import unittest

from core.pompage.champ import (
    MENTION_TEMPERATURES_REPLI, choisir_variateur, dimensionner_champ,
    e_d_depuis_profils, kw_normalise_depuis_cv, kwc_depart,
)
from core.pompage.hypotheses import valeur
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
        # AGQ6 (réaligné) — 3 CV × 0,7355 = 2,21 kW, arrondi au moteur
        # normalisé 2,2 kW (IEC 60034-1) : jamais « aucun variateur ».
        res = choisir_variateur(CATALOGUE, cv="3", alimentation="mono")
        codes = [a["code"] for a in res["alertes"]]
        self.assertIn("kw_plaque_a_relever", codes)
        self.assertNotIn("aucun_variateur", codes)
        self.assertIsNotNone(res["variateur"])

    def test_cv_hors_puissance_normalisee_jamais_arrondi_vers_le_bas(self):
        # 12,5 CV = 9,19 kW : aucune puissance normalisée dans la tolérance
        # d'arrondi du CV écrit ⇒ 9,19 kW requis, variateur ≥ 9,19 kW.
        res = choisir_variateur(CATALOGUE + [_var(8, 11, 380)], cv="12.5",
                                alimentation="tri")
        self.assertEqual(res["kw_requis"], 9.19)
        self.assertEqual(res["variateur"]["id"], 8)

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


class Variateur(unittest.TestCase):
    """AGQ6 (C-AGQ-005) — pompe connue par son seul CV."""

    def test_3cv_mono_cv_seul_retient_le_2_2_kw(self):
        res = choisir_variateur(CATALOGUE, cv="3.00", alimentation="mono")
        self.assertIsNotNone(res["variateur"])
        self.assertEqual(res["variateur"]["id"], 1)  # SI22 2,2 kW 220 V
        self.assertEqual(res["kw_requis"], 2.2)
        self.assertEqual(res["source_kw"], "cv")
        codes = [a["code"] for a in res["alertes"]]
        self.assertIn("kw_plaque_a_relever", codes)
        self.assertIn("kw_moteur_normalises",
                      [h["cle"] for h in res["hypotheses"]])

    def test_agm1_5_5cv_est_le_moteur_normalise_4kw(self):
        # AGM1 (D-AGM-1) — 5,5 CV = 4,045 kW (1,1 % de 4 kW) : moteur 4 kW,
        # donc le variateur 4 kW et non le 5,5 kW de la valeur brute.
        res = choisir_variateur(CATALOGUE, cv="5.5", alimentation="tri")
        self.assertEqual(res["kw_requis"], 4.0)
        self.assertEqual(res["variateur"]["id"], 4)

    def test_agm1_cv_hors_2_pct_reste_brut(self):
        # 12,5 CV = 9,19 kW et 63 CV = 46,34 kW : plus de 2 % d'une puissance
        # normalisée ⇒ le kW calculé reste tel quel.
        self.assertEqual(kw_normalise_depuis_cv("12.5"),
                         (12.5 * 0.7355, False))
        kw, normalise = kw_normalise_depuis_cv("63")
        self.assertFalse(normalise)
        self.assertAlmostEqual(kw, 63 * 0.7355)

    def test_agm1_balayage_cv_vers_moteur_iec(self):
        attendu = {1: 0.75, 1.5: 1.1, 2: 1.5, 3: 2.2, 4: 3, 5.5: 4, 7.5: 5.5,
                   10: 7.5, 15: 11, 20: 15, 25: 18.5, 30: 22, 40: 30, 50: 37,
                   60: 45, 75: 55, 100: 75}
        normalises = set(valeur("kw_moteur_normalises"))
        for cv, iec in attendu.items():
            kw, normalise = kw_normalise_depuis_cv(str(cv))
            self.assertTrue(normalise, cv)
            self.assertEqual(kw, float(iec), cv)
            self.assertIn(iec, normalises)


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


class Couverture(unittest.TestCase):
    """AGQ2 (D-AGQ-2) — mois critique = pire mois RÉEL de production."""

    BESOIN = [0.0] * 3 + [120.0] * 7 + [0.0] * 2  # avril → octobre

    def test_mois_critique_est_le_pire_mois_de_production(self):
        # Le mois 4 (avril) est celui que désignait la forme du profil
        # (heures-pic identiques sur la saison) : il n'est qu'une indication.
        res = dimensionner_champ(
            besoin_m3_jour_mois=self.BESOIN, hmt_m=70, panneau=PANNEAU,
            variateurs_candidats=[_var(30, 7.5, 380)],
            pompe={"courbe_pompe": OSP_30_8}, p_plaque_kw=7.5,
            profils_horaires=PROFILS, mois_critique=4)
        self.assertEqual(res["mois_critique"], 10)  # octobre
        prod = res["production"]["m3_jour_mois"]
        for i in range(3, 10):
            self.assertGreaterEqual(prod[i], 120.0, "mois %d" % (i + 1))


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

    def _osp(self, besoin, hmt):
        return dimensionner_champ(
            besoin_m3_jour_mois=[float(besoin)] * 12, hmt_m=hmt,
            panneau=PANNEAU, variateurs_candidats=[_var(30, 7.5, 380)],
            pompe={"courbe_pompe": OSP_30_8}, p_plaque_kw=7.5,
            profils_horaires=PROFILS)

    def test_agm2_besoin_incouvrable_repli_borne_a_1_5_fois_la_plaque(self):
        # OSP 30/8 7,5 kW, 800 m3/j a 70 m : jamais couvrable. Avant : repli
        # = kWc de depart = 121 panneaux (ratio 11,45) ; borne = ⌈1,5 × 7,5 ×
        # 1000 / 710⌉ = 16 panneaux.
        res = self._osp(800, 70)
        borne = math.ceil(1.5 * 7.5 * 1000 / 710)
        self.assertEqual(borne, 16)
        self.assertLess(borne, math.ceil(res["kwc_depart"] * 1000 / 710))
        self.assertEqual(res["nb_panneaux"], borne)
        alerte = [a for a in res["alertes"]
                  if a["code"] == "besoin_non_couvert_champ"]
        self.assertEqual(len(alerte), 1)
        self.assertIn("borne de 1,5 × la plaque de 7,5 kW", alerte[0]["message"])
        self.assertIn("16 panneaux", alerte[0]["message"])
        # La couverture affichee est l'honnete (< besoin), jamais masquee.
        self.assertLess(res["production"]["m3_jour_mois"][11], 800)

    def test_agm2_cas_couvrable_inchange(self):
        # 200 m3/j a 58,7 m : la recherche trouve un champ qui couvre (18
        # panneaux, mesure d'avant AGM2) ; aucune alerte « non couvert ».
        res = self._osp(200, 58.7)
        self.assertEqual(res["nb_panneaux"], 18)
        self.assertNotIn("besoin_non_couvert_champ",
                         [a["code"] for a in res["alertes"]])
        self.assertGreaterEqual(res["production"]["m3_jour_mois"][11], 200.0)

    def _codes_non_dimensionne(self, **kwargs):
        params = dict(besoin_m3_jour_mois=[20.0] * 12, hmt_m=40,
                      panneau=PANNEAU, variateurs_candidats=[_var(31, 7.5, 380)],
                      p_plaque_kw=7.5, profils_horaires=PROFILS)
        params.update(kwargs)
        res = dimensionner_champ(**params)
        self.assertIsNone(res["nb_panneaux"])
        return res, [a["code"] for a in res["alertes"]]

    def test_agm3_hmt_inconnue_nomme_la_vraie_cause(self):
        for hmt in (None, 0, -5):
            res, codes = self._codes_non_dimensionne(hmt_m=hmt)
            self.assertIn("hmt_inconnue", codes, hmt)
            self.assertNotIn("irradiation_inconnue", codes, hmt)
            self.assertIn("HMT", res["chaines"]["motif"])

    def test_agm3_besoin_nul_nomme_la_vraie_cause(self):
        res, codes = self._codes_non_dimensionne(
            besoin_m3_jour_mois=[0.0] * 12)
        self.assertIn("besoin_nul", codes)
        self.assertNotIn("irradiation_inconnue", codes)

    def test_agm3_sans_profil_irradiation_inconnue_inchange(self):
        res, codes = self._codes_non_dimensionne(profils_horaires=None)
        self.assertIn("irradiation_inconnue", codes)
        self.assertEqual(res["chaines"]["motif"], "irradiation inconnue")

    def test_agm3_les_deux_codes_rejoignent_la_liste_du_domaine(self):
        from apps.ventes.domain.pompage import CODES_CHAMP_NON_DIMENSIONNE
        self.assertIn("hmt_inconnue", CODES_CHAMP_NON_DIMENSIONNE)
        self.assertIn("besoin_nul", CODES_CHAMP_NON_DIMENSIONNE)
        self.assertIn("irradiation_inconnue", CODES_CHAMP_NON_DIMENSIONNE)

    def test_agm4_coefficients_absents_alerte_nommee(self):
        sans = {k: v for k, v in PANNEAU.items()
                if k != "temp_coeff_voc_pct_c"}
        params = dict(besoin_m3_jour_mois=[20.0] * 12, hmt_m=40,
                      variateurs_candidats=[_var(32, 4, 380,
                                                 fiche=FICHE_250_780)],
                      p_plaque_kw=3, profils_horaires=PROFILS)
        res = dimensionner_champ(panneau=sans, **params)
        alerte = [a for a in res["alertes"]
                  if a["code"] == "coefficients_temperature_non_sources"]
        self.assertEqual(len(alerte), 1)
        self.assertIn("temp_coeff_voc_pct_c = -0,27", alerte[0]["message"])
        self.assertNotIn("temp_coeff_pmax_pct_c", alerte[0]["message"])
        self.assertTrue(res["chaines"]["verifiable"])
        # Panneau complet : aucune alerte.
        complet = dimensionner_champ(panneau=PANNEAU, **params)
        self.assertNotIn("coefficients_temperature_non_sources",
                         [a["code"] for a in complet["alertes"]])

    def test_agm4_fiche_variateur_non_saisie_pas_d_alerte_coefficients(self):
        # Chaîne non calculée : rien à marquer (l'alerte chaine_non_verifiable
        # est déjà là).
        sans = {k: v for k, v in PANNEAU.items()
                if not k.startswith("temp_coeff")}
        res = dimensionner_champ(
            besoin_m3_jour_mois=[20.0] * 12, hmt_m=40, panneau=sans,
            variateurs_candidats=[_var(33, 4, 380)], p_plaque_kw=3,
            profils_horaires=PROFILS)
        self.assertNotIn("coefficients_temperature_non_sources",
                         [a["code"] for a in res["alertes"]])

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
