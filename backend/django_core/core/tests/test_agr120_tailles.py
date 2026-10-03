# -*- coding: utf-8 -*-
"""AGR120 — trois tailles tirées du catalogue + hectares irrigables (noyau
pur, sans base).

Pompes : courbes OSP 30/8, 30/11, 30/13 recopiées du seed
(``seed_catalogue.py``) mais rendues CHIFFRABLES pour le test (dans le seed
elles sont à prix 0, QXG3) ; « Pompe test 4 kW » = donnée de test. Profils
horaires SYNTHÉTIQUES.
"""

import unittest

from core.pompage.agronomie import besoin_agronomique
from core.pompage.selection import choisir_pompe
from core.pompage.tailles import (
    MOTIF_EXISTANTE, MOTIF_HA_VOLUME, MOTIF_INFERIEURE, proposer_tailles,
)
from core.pompage.volumes import _CLEARSKY_HOURLY_SHAPE

PIC = max(_CLEARSKY_HOURLY_SHAPE)
PICS = (650, 720, 820, 900, 950, 980, 990, 960, 880, 780, 680, 630)
PROFILS = tuple(tuple(f / PIC * g for f in _CLEARSKY_HOURLY_SHAPE)
                for g in PICS)

DEBITS = [0, 12, 24, 30, 36, 39]


def _pompe(id_, nom, kw, hmt=None, debits=DEBITS):
    return {"id": id_, "nom": nom, "role_pompage": "pompe",
            "type_pompe": "immergee", "alimentation": "tri",
            "pompe_kw": str(kw), "tension_v": 380,
            "courbe_pompe": {"debits_m3h": debits, "hmt_m": hmt},
            "fiche": None, "prix_connu": True}


POMPES = [
    _pompe(50, "Pompe immergée test 4 kW (380V)", 4, [90, 80, 62, 50],
           [0, 6, 12, 15]),
    _pompe(314, "Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3\", 380V)", 7.5,
           [91, 85, 70, 60, 43, 34]),
    _pompe(315, "Pompe immergée OSP 30/11 — 12.5 CV / 9.3 kW (3\", 380V)",
           9.3, [125, 117, 97, 83, 59, 46]),
    _pompe(316, "Pompe immergée OSP 30/13 — 15 CV / 11 kW (3\", 380V)", 11,
           [148, 138, 114, 98, 70, 55]),
]


def _var(id_, kw):
    return {"id": id_, "nom": "VARIATEUR VEICHI SI23 %sKW 380V" % kw,
            "role_pompage": "variateur_pompage", "pompe_kw": str(kw),
            "tension_v": 380, "fiche": None, "prix_connu": True}


VARIATEURS = [_var(1, 4), _var(2, 7.5), _var(3, 11)]
PANNEAU = {"id": 3, "nom": "Panneau 710W", "pmax_wc": 710, "vmp_v": 40.4,
           "voc_v": 48.6, "isc_a": 18.6, "imp_a": 17.6, "prix_connu": True}
KIT = {"structure": {"id": 51, "nom": "Structure au sol", "prix_connu": True}}

BESOIN = [135.0] * 12
HMT = 58.7


def _neuve(**extra):
    choix = choisir_pompe(POMPES, hmt_m=HMT, debit_conception_m3h=25,
                          alimentation="tri")
    params = dict(choix_pompe=choix, besoin_m3_jour_mois=BESOIN, hmt_m=HMT,
                  alimentation="tri", variateurs=VARIATEURS, panneau=PANNEAU,
                  profils_horaires=PROFILS, kit=KIT)
    params.update(extra)
    return choix, proposer_tailles(**params)


class TroisTailles(unittest.TestCase):

    def test_catalogue_a_3_paliers_tailles_ordonnees(self):
        choix, res = _neuve()
        self.assertEqual(choix["pompe"]["produit"], 314)
        self.assertEqual([t["cle"] for t in res["tailles"]],
                         ["inferieure", "recommandee", "superieure"])
        self.assertEqual([t["pompe_produit"] for t in res["tailles"]],
                         [50, 314, 315])
        self.assertEqual(res["defaut"], "recommandee")
        recommandee = res["tailles"][1]
        self.assertTrue(recommandee["retenue"])
        self.assertGreaterEqual(recommandee["couverture_mois_critique_pct"],
                                95)
        # Couverture de l'inférieure AFFICHÉE (jamais masquée) ; son débit à
        # la HMT est sous le débit de conception (12,8 < 25 m³/h).
        self.assertIsNotNone(
            res["tailles"][0]["couverture_mois_critique_pct"])
        self.assertLess(res["tailles"][0]["puissance_kw"],
                        recommandee["puissance_kw"])
        self.assertFalse(res["tailles"][0]["retenue"])
        # Composition AGR119 portée par chaque taille.
        cles = [x["cle"] for x in recommandee["composition"]["inclus"]]
        self.assertEqual(cles[:3], ["pompe", "variateur", "panneaux"])
        self.assertEqual(len(recommandee["m3_jour_mois"]), 12)

    def test_palier_absent_omis_avec_motif(self):
        choix = choisir_pompe(POMPES[1:3], hmt_m=HMT,
                              debit_conception_m3h=25, alimentation="tri")
        res = proposer_tailles(
            choix_pompe=choix, besoin_m3_jour_mois=BESOIN, hmt_m=HMT,
            alimentation="tri", variateurs=VARIATEURS, panneau=PANNEAU,
            profils_horaires=PROFILS, kit=KIT)
        self.assertEqual([t["cle"] for t in res["tailles"]],
                         ["recommandee", "superieure"])
        self.assertEqual(res["tailles_omises"],
                         [{"cle": "inferieure", "motif": MOTIF_INFERIEURE}])

    def test_aucune_pompe_chiffrable_trois_omises(self):
        choix = choisir_pompe([], hmt_m=HMT, debit_conception_m3h=25,
                              alimentation="tri")
        res = proposer_tailles(choix_pompe=choix, besoin_m3_jour_mois=BESOIN,
                               hmt_m=HMT, alimentation="tri",
                               variateurs=VARIATEURS, panneau=PANNEAU)
        self.assertEqual(res["tailles"], [])
        self.assertEqual(len(res["tailles_omises"]), 3)


class Hectares(unittest.TestCase):

    def test_ha_derives_et_etiquetes_estimation(self):
        agro = besoin_agronomique(
            [{"culture": "olivier", "surface_ha": 4, "methode": "goutte"}],
            region="tadla")
        _choix, res = _neuve(besoin_m3_jour_mois=agro["m3_jour_mois"],
                             besoin_agronomique=agro)
        ha = res["tailles"][1]["ha_irrigables"]
        self.assertIsNotNone(ha["valeur"])
        self.assertIn("estimation", ha["motif"])
        taille = res["tailles"][1]
        mois = taille["champ"]["mois_critique"]
        attendu = round(taille["m3_jour_mois"][mois - 1]
                        / agro["m3_ha_jour_mois"][mois - 1], 1)
        self.assertEqual(ha["valeur"], attendu)

    def test_besoin_declare_aucun_ha(self):
        _choix, res = _neuve()
        ha = res["tailles"][1]["ha_irrigables"]
        self.assertIsNone(ha["valeur"])
        self.assertEqual(ha["motif"], MOTIF_HA_VOLUME)


class Existante(unittest.TestCase):

    def test_une_seule_taille_avec_motif(self):
        res = proposer_tailles(
            mode_pompe="existante",
            plaque={"kw": 4, "tension_v": 380, "phases": 3},
            debit_declare_m3h=12, besoin_m3_jour_mois=[60.0] * 12,
            hmt_m=50, variateurs=VARIATEURS, panneau=PANNEAU,
            profils_horaires=PROFILS, kit=KIT)
        self.assertEqual(len(res["tailles"]), 1)
        taille = res["tailles"][0]
        self.assertEqual(taille["motif"], MOTIF_EXISTANTE)
        self.assertIsNone(taille["pompe_produit"])
        self.assertNotIn("pompe", [x["cle"] for x in
                                   taille["composition"]["inclus"]])
        self.assertEqual({o["cle"] for o in res["tailles_omises"]},
                         {"inferieure", "superieure"})


if __name__ == "__main__":
    unittest.main()
