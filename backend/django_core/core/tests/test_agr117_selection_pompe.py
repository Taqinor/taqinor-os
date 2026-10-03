# -*- coding: utf-8 -*-
"""AGR117 — pompe neuve choisie sur le débit de conception (noyau pur).

Catalogue ILLUSTRATIF recopié du seed (``seed_catalogue.py`` : pompes
génériques POMPAGE à prix public, sans courbe ; OSP 30 à courbe, prix 0). La
« petite pompe à courbe » est une donnée de test.
"""

import ast
import os
import unittest

from core.pompage.selection import (
    ETIQUETTE_A_CONFIRMER, PREFIXE_PLACEHOLDER, choisir_pompe,
)

OSP_30_8 = {"id": 314, "nom": "Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3\", 380V)",
            "role_pompage": "pompe", "type_pompe": "immergee",
            "alimentation": "tri", "pompe_cv": "10.00", "pompe_kw": "7.50",
            "tension_v": 380,
            "courbe_pompe": {"debits_m3h": [0, 12, 24, 30, 36, 39],
                             "hmt_m": [91, 85, 70, 60, 43, 34]},
            "fiche": None, "prix_connu": False}


def _generique(id_, cv, alim, prix=True, type_pompe="immergee"):
    libelle = "Monophasé" if alim == "mono" else "Triphasé"
    mot = "immergée" if type_pompe == "immergee" else "de surface"
    return {"id": id_, "nom": "Pompe %s solaire %s CV %s" % (mot, cv, libelle),
            "role_pompage": "pompe", "type_pompe": type_pompe,
            "alimentation": alim, "pompe_cv": str(cv), "pompe_kw": None,
            "tension_v": None, "courbe_pompe": None, "fiche": None,
            "prix_connu": prix}


GENERIQUES = [
    _generique(1, 1.5, "mono"), _generique(2, 3, "mono"),
    _generique(3, 4, "tri"), _generique(4, 5.5, "tri"),
    _generique(5, 7.5, "tri"), _generique(6, 10, "tri"),
]


def _petite_courbe(prix=True):
    return {"id": 50, "nom": "Pompe immergée test 4 kW (380V)",
            "role_pompage": "pompe", "type_pompe": "immergee",
            "alimentation": "tri", "pompe_kw": "4", "tension_v": 380,
            "courbe_pompe": {"debits_m3h": [0, 6, 12, 15],
                             "hmt_m": [90, 80, 62, 50]},
            "fiche": None, "prix_connu": prix}


class QuatreCas(unittest.TestCase):

    def test_osp_prix_0_jamais_aucune_ligne_pompe(self):
        """HMT 60 / 10 m³/h, OSP à prix 0 : avant, aucune ligne pompe."""
        res = choisir_pompe(GENERIQUES + [OSP_30_8], hmt_m=60,
                            debit_conception_m3h=10, alimentation="tri")
        self.assertIsNotNone(res["pompe"]["nom"])
        self.assertFalse(res["pompe"]["placeholder"])
        self.assertEqual(res["etape"], "pre_dimensionnement")
        # kW min = 10 × 60 × 2,725 / (1000 × 0,35) = 4,67 kW ⇒ 7,5 CV (5,52)
        # (rendement_groupe = 0,35, décision fondateur du 03/10/2026).
        self.assertEqual(res["pompe"]["produit"], 5)
        self.assertEqual(res["pompe"]["etiquette"], ETIQUETTE_A_CONFIRMER)
        self.assertFalse(res["production_publiable"])
        self.assertIn(OSP_30_8["nom"], res["prix_a_renseigner"])

    def test_rien_de_price_placeholder_nomme(self):
        res = choisir_pompe([OSP_30_8], hmt_m=60, debit_conception_m3h=10,
                            alimentation="tri")
        self.assertTrue(res["pompe"]["placeholder"])
        self.assertIsNone(res["pompe"]["produit"])
        self.assertEqual(res["pompe"]["nom"],
                         PREFIXE_PLACEHOLDER + OSP_30_8["nom"])
        self.assertFalse(res["pompe"]["prix_connu"])
        self.assertIn("aucune_pompe_chiffrable",
                      [a["code"] for a in res["alertes"]])

    def test_mono_jamais_triphasee(self):
        """Demande mono au-delà de la gamme : jamais une pompe tri."""
        res = choisir_pompe(GENERIQUES, hmt_m=60, debit_conception_m3h=10,
                            alimentation="mono")
        self.assertNotEqual(res["pompe"]["alimentation"], "tri")
        self.assertTrue(res["pompe"]["placeholder"])
        gamme = [a for a in res["alertes"] if a["code"] == "gamme_monophasee"]
        self.assertTrue(gamme)
        # 3 CV × 0,7355 = 2,21 kW, le plus gros mono du catalogue.
        self.assertIn("2,21 kW max", gamme[0]["message"])

    def test_mono_hors_courbe_jamais_silencieux(self):
        res = choisir_pompe(GENERIQUES, hmt_m=40, debit_conception_m3h=3,
                            alimentation="mono")
        self.assertEqual(res["pompe"]["produit"], 1)
        self.assertEqual(res["pompe"]["alimentation"], "mono")
        self.assertIsNone(res["pompe"]["courbe"])
        self.assertIn("pompe_sans_courbe", [a["code"] for a in res["alertes"]])
        self.assertIn("kw_plaque_a_relever",
                      [a["code"] for a in res["alertes"]])

    def test_plus_petite_pompe_a_courbe_qui_couvre(self):
        osp_price = dict(OSP_30_8, prix_connu=True)
        res = choisir_pompe([osp_price, _petite_courbe()], hmt_m=60,
                            debit_conception_m3h=10, alimentation="tri")
        self.assertEqual(res["etape"], "courbe")
        self.assertEqual(res["pompe"]["produit"], 50)
        self.assertTrue(res["production_publiable"])
        self.assertEqual([p["id"] for p in res["paliers"]], [50, 314])
        self.assertEqual(res["index_palier"], 0)

    def test_surlivraison_servie_a_cote_du_demande(self):
        """10 m³/h demandés, seule l'OSP 30/8 (30 m³/h à 60 m) : la couverture
        est EXPOSÉE, jamais cachée ni bloquée par un seuil."""
        osp_price = dict(OSP_30_8, prix_connu=True)
        res = choisir_pompe([osp_price], hmt_m=60, debit_conception_m3h=10,
                            alimentation="tri")
        self.assertEqual(res["couverture"]["debit_demande_m3h"], 10)
        self.assertEqual(res["couverture"]["debit_livre_m3h"], 30)
        self.assertEqual(res["couverture"]["couverture_pct"], 300)
        self.assertEqual(res["puissance_retenue"], {"kw": 7.5, "cv": 10.2})


class Gardes(unittest.TestCase):

    def test_composition_neuve_toujours_pompe_ou_placeholder(self):
        cas = [([], 60, 10, "tri"), (GENERIQUES, 60, 10, "mono"),
               ([OSP_30_8], 60, 10, "tri"), (GENERIQUES, None, 10, "tri"),
               (GENERIQUES, 60, 10, "tri")]
        for pompes, hmt, q, alim in cas:
            res = choisir_pompe(pompes, hmt_m=hmt, debit_conception_m3h=q,
                                alimentation=alim)
            pompe = res["pompe"]
            self.assertTrue(pompe["nom"])
            self.assertTrue(pompe["placeholder"] or pompe["produit"])

    def test_surface_jamais_immergee(self):
        cat = GENERIQUES + [_generique(7, 1.5, "mono", type_pompe="surface")]
        res = choisir_pompe(cat, hmt_m=20, debit_conception_m3h=2,
                            alimentation="mono", type_pompe="surface")
        self.assertEqual(res["pompe"]["produit"], 7)

    def test_alimentation_inconnue_jamais_candidate(self):
        inconnue = dict(_generique(8, 5.5, "tri"), alimentation="",
                        nom="Pompe immergée solaire 5.5 CV")
        res = choisir_pompe([inconnue], hmt_m=60, debit_conception_m3h=10,
                            alimentation="tri")
        self.assertTrue(res["pompe"]["placeholder"])

    def test_diametre_et_immersion_alertes(self):
        p = dict(_petite_courbe(), fiche={"pompe_diametre_ext_mm": 150,
                                          "pompe_immersion_min_m": 5})
        res = choisir_pompe([p], hmt_m=60, debit_conception_m3h=10,
                            alimentation="tri", diametre_tubage_mm=150,
                            profondeur_calage_m=42, niveau_dynamique_m=40)
        codes = [a["code"] for a in res["alertes"]]
        self.assertIn("diametre_tubage", codes)
        self.assertIn("immersion_minimale", codes)


def _liste_seed(nom_liste):
    chemin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "apps", "stock", "management",
        "commands", "seed_catalogue.py")
    with open(chemin, encoding="utf-8") as fichier:
        arbre = ast.parse(fichier.read())
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and any(
                getattr(c, "id", None) == nom_liste for c in noeud.targets):
            return ast.literal_eval(noeud.value)
    raise AssertionError(nom_liste)


class CouvertureCatalogue(unittest.TestCase):

    @unittest.expectedFailure
    def test_une_pompe_pricee_a_courbe_par_alimentation(self):
        """QXG3 (étendu par AGRM1) : le seed n'a AUCUNE pompe à courbe
        pricée — les 11 OSP 30 sont à prix 0 et triphasées, les pompes
        génériques n'ont pas de courbe. Échec ATTENDU tant que QXG3 est
        ouvert ; ce test passera au vert (et devra perdre son décorateur)
        quand le fondateur aura chiffré une pompe à courbe par alimentation."""
        from core.pompage.selection import alimentation_produit

        pricees_a_courbe = set()
        # OSP : (nom, sku, cv, kw, courbe[, prix]) — le seed n'a pas de
        # colonne prix (prix 0) ; un prix ajouté en 6e colonne compterait.
        for ligne in _liste_seed("OSP"):
            prix = ligne[5] if len(ligne) > 5 else 0
            if ligne[4] and prix and prix > 0:
                pricees_a_courbe.add(alimentation_produit({"nom": ligne[0]}))
        # POMPAGE : (nom, sku, ttc, qte, seuil, cv, hmt, debit) — aucune
        # colonne courbe : jamais « à courbe ».
        for ligne in _liste_seed("POMPAGE"):
            self.assertEqual(len(ligne), 8)
        self.assertTrue({"mono", "tri"} <= pricees_a_courbe)


if __name__ == "__main__":
    unittest.main()
