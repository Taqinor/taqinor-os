# -*- coding: utf-8 -*-
"""AGR118 — pompe existante conservée (D-AGR-7) : variateur et champ sur la
PLAQUE (noyau pur, sans base).

Variateurs ILLUSTRATIFS recopiés du seed (``seed_catalogue.py`` VEICHI : le
plus gros 220 V est un 2,2 kW). Profils horaires SYNTHÉTIQUES.
"""

import unittest

from core.pompage.conception import NOM_POMPE_EXISTANTE, pompe_existante
from core.pompage.selection import variateurs_compatibles_plaque
from core.pompage.volumes import _CLEARSKY_HOURLY_SHAPE

PIC = max(_CLEARSKY_HOURLY_SHAPE)
PICS = (650, 720, 820, 900, 950, 980, 990, 960, 880, 780, 680, 630)
PROFILS = tuple(tuple(f / PIC * g for f in _CLEARSKY_HOURLY_SHAPE)
                for g in PICS)

PANNEAU = {"id": 3, "nom": "Panneau 710W", "pmax_wc": 710, "vmp_v": 40.4,
           "voc_v": 48.6, "isc_a": 18.6, "imp_a": 17.6}


def _var(id_, kw, tension, fiche=None):
    return {"id": id_, "nom": "VARIATEUR VEICHI SI23 %sKW %sV" % (kw, tension),
            "role_pompage": "variateur_pompage", "pompe_kw": str(kw),
            "tension_v": tension, "fiche": fiche, "prix_connu": True}


VARIATEURS = [_var(1, 2.2, 220), _var(2, 2.2, 380), _var(3, 4, 380),
              _var(4, 5.5, 380)]


class PompeExistante(unittest.TestCase):

    def test_plaque_2_2_mono_220_variateur_220_et_zero_ligne_pompe(self):
        res = pompe_existante(
            plaque={"kw": 2.2, "tension_v": 220, "phases": 1},
            variateurs=VARIATEURS)
        self.assertEqual(res["variateur"]["produit"], 1)
        self.assertEqual(res["variateur"]["kw"], 2.2)
        self.assertEqual(res["variateur"]["tension_v"], 220)
        pompe = res["pompe"]
        self.assertEqual(pompe["mode"], "existante")
        self.assertIsNone(pompe["produit"])
        self.assertFalse(pompe["placeholder"])
        self.assertEqual(pompe["nom"], NOM_POMPE_EXISTANTE)
        self.assertEqual(res["prix_a_renseigner"], [])

    def test_plaque_4_mono_220_alerte_aucun_variateur(self):
        res = pompe_existante(
            plaque={"kw": 4, "tension_v": 220, "phases": 1},
            variateurs=VARIATEURS)
        self.assertIsNone(res["variateur"]["produit"])
        messages = [a["message"] for a in res["alertes"]
                    if a["code"] == "aucun_variateur"]
        self.assertTrue(messages)
        self.assertIn("Aucun variateur 220 V ≥ 4 kW au catalogue",
                      messages[0])

    def test_cv_seul_alerte_kw_plaque_et_aucun_variateur(self):
        res = pompe_existante(plaque={"cv": 3, "phases": 1},
                              variateurs=VARIATEURS)
        self.assertIn("kw_plaque_a_relever",
                      [a["code"] for a in res["alertes"]])
        self.assertIsNone(res["variateur"]["produit"])
        # Affichage seulement : 3 × 0,7355 = 2,21 kW.
        self.assertEqual(res["puissance_retenue"], {"kw": 2.21, "cv": 3})

    def test_sans_debit_declare_production_null(self):
        res = pompe_existante(
            plaque={"kw": 4, "tension_v": 380, "phases": 3},
            variateurs=VARIATEURS, panneau=PANNEAU,
            besoin_m3_jour_mois=[60.0] * 12, hmt_m=50,
            profils_horaires=PROFILS)
        self.assertIsNone(res["production"])
        self.assertIsNotNone(res["champ"]["nb_panneaux"])
        self.assertIn("production_omise", [a["code"] for a in res["alertes"]])

    def test_debit_declare_production_estimee_etiquetee(self):
        res = pompe_existante(
            plaque={"kw": 4, "tension_v": 380, "phases": 3},
            variateurs=VARIATEURS, panneau=PANNEAU,
            besoin_m3_jour_mois=[60.0] * 12, hmt_m=50,
            debit_declare_m3h=12, profils_horaires=PROFILS)
        self.assertEqual(res["production"]["mode"], "debit_declare")
        self.assertEqual(res["variateur"]["produit"], 3)

    def test_tri_220_sans_fiche_compatibilite_a_verifier(self):
        res = pompe_existante(
            plaque={"kw": 2.2, "tension_v": 220, "phases": 3},
            variateurs=VARIATEURS)
        self.assertEqual(res["variateur"]["produit"], 1)
        self.assertIn("compatibilite_a_verifier",
                      [a["code"] for a in res["alertes"]])

    def test_tri_220_fiche_publiee_retenue_sans_alerte(self):
        fiche = {"var_v_sortie_v": 220, "ond_phases": 3}
        cat = VARIATEURS + [_var(9, 2.2, 220, fiche=fiche)]
        res = pompe_existante(
            plaque={"kw": 2.2, "tension_v": 220, "phases": 3}, variateurs=cat)
        self.assertEqual(res["variateur"]["produit"], 9)
        self.assertNotIn("compatibilite_a_verifier",
                         [a["code"] for a in res["alertes"]])


class CompatibiliteSortie(unittest.TestCase):

    def test_mono_220_ecarte_sortie_triphasee_publiee(self):
        cat = [_var(1, 2.2, 220, fiche={"ond_phases": 3}), _var(2, 2.2, 220)]
        ok, a_verifier = variateurs_compatibles_plaque(cat, tension_v=220,
                                                       phases=1)
        self.assertEqual([v["id"] for v in ok], [2])
        self.assertEqual(a_verifier, [])

    def test_380_jamais_pour_une_plaque_220(self):
        ok, a_verifier = variateurs_compatibles_plaque(VARIATEURS,
                                                       tension_v=220, phases=1)
        self.assertEqual([v["id"] for v in ok], [1])


if __name__ == "__main__":
    unittest.main()
