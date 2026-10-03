# -*- coding: utf-8 -*-
"""AGR119 — kit pompage « minimum + options nommées » (D-AGR-8), noyau pur.

Catalogue ILLUSTRATIF calqué sur le seed (``seed_catalogue.py`` : options
AGR104 et SKU AGR620 à prix VIDE, INST-CAT à barème toiture, afficheur SI22).
"""

import unittest

from core.pompage.kit import (
    MENTION_COMPTEUR, OPTIONS, SUFFIXE_PRIX, composer_kit,
)

POMPE = {"mode": "neuve", "produit": 314, "nom": "Pompe immergée test 4 kW",
         "placeholder": False, "prix_connu": True}
VARIATEUR = {"id": 403, "nom": "VARIATEUR VEICHI SI23 7.5KW 380V",
             "role_pompage": "variateur_pompage", "prix_connu": True}
PANNEAU = {"id": 3, "nom": "Panneau 710W", "prix_connu": True}
STRUCTURE = {"id": 51, "nom": "Structure au sol acier", "prix_connu": True}
INST_CAT = {"id": 61, "nom": "Installation", "prix_connu": True}
INST_PMP_VIDE = {"id": 60, "nom": "Installation pompage solaire",
                 "role_pompage": "installation_pompage", "prix_connu": False,
                 "prix_fixe_ht": None, "prix_par_panneau_ht": None}
TRANSPORT = {"id": 62, "nom": "Transport", "prix_connu": True}


def _option(id_, nom, role, prix=False):
    return {"id": id_, "nom": nom, "role_pompage": role, "prix_connu": prix}


OPTIONS_SEED = [
    _option(420, "AFFICHEUR VARIATEUR SI22", "afficheur_variateur", True),
    _option(71, "Sonde de niveau (protection marche à sec)", "sonde_niveau"),
    _option(72, "Compteur d'eau / débitmètre", "compteur_eau"),
    _option(73, "Câble de descente immergé (au mètre)", "cable_descente"),
    _option(74, "Colonne de refoulement", "colonne_refoulement"),
    _option(75, "Clapet anti-retour", "clapet"),
    _option(76, "Tuyauterie (au mètre)", "tuyauterie"),
    _option(77, "Bassin", "bassin"),
    _option(78, "Contrat d'entretien et maintenance pompage solaire",
            "entretien_pompage"),
    _option(79, "Fixations antivol (visserie inviolable)", "antivol"),
    _option(80, "Clôture du champ solaire", "cloture"),
]

BASE = dict(mode_pompe="neuve", pompe=POMPE, variateur=VARIATEUR,
            panneau=PANNEAU, nb_panneaux=14, structure=STRUCTURE,
            installation_pompage=INST_PMP_VIDE, installation_toiture=INST_CAT,
            transport=TRANSPORT, produits_options=OPTIONS_SEED)


def _cles(kit):
    return [ligne["cle"] for ligne in kit["inclus"]]


def _option_par_cle(kit, cle):
    return next(o for o in kit["options"] if o["cle"] == cle)


class KitMinimal(unittest.TestCase):

    def test_kit_neuf_minimal(self):
        kit = composer_kit(**BASE)
        self.assertEqual(_cles(kit), ["pompe", "variateur", "panneaux",
                                      "structure", "installation",
                                      "transport"])
        self.assertEqual(kit["inclus"][2]["quantite"], 14)
        self.assertEqual(kit["inclus"][3]["quantite"], 14)

    def test_non_inclus_present(self):
        self.assertEqual(composer_kit(**BASE)["non_inclus"],
                         ["forage", "genie_civil"])

    def test_zero_batterie_zero_onduleur(self):
        kit = composer_kit(**dict(BASE, options_cochees=[
            o[0] for o in OPTIONS]))
        for ligne in kit["lignes"] + kit["inclus"]:
            texte = (ligne["designation"] or "").lower()
            self.assertNotIn("batterie", texte)
            self.assertNotIn("onduleur", texte)

    def test_mode_existante_aucune_ligne_pompe(self):
        kit = composer_kit(**dict(BASE, mode_pompe="existante"))
        self.assertNotIn("pompe", _cles(kit))
        self.assertIn("variateur", _cles(kit))

    def test_pompe_placeholder_seule(self):
        placeholder = {"mode": "neuve", "produit": None, "placeholder": True,
                       "nom": "Pompe — prix à renseigner : OSP 30/8",
                       "prix_connu": False}
        kit = composer_kit(**dict(BASE, pompe=placeholder))
        self.assertEqual(_cles(kit), ["pompe"])
        self.assertEqual(kit["inclus"][0]["designation"], placeholder["nom"])
        self.assertIsNone(kit["inclus"][0]["produit"])


class Installation(unittest.TestCase):

    def test_catalogue_de_seed_inst_cat_et_alerte_interne(self):
        kit = composer_kit(**BASE)
        ligne = next(x for x in kit["inclus"] if x["cle"] == "installation")
        self.assertEqual(ligne["produit"], 61)
        alerte = [a for a in kit["alertes"]
                  if a["code"] == "bareme_installation_toiture"]
        self.assertTrue(alerte)
        self.assertTrue(alerte[0]["interne"])

    def test_inst_pmp_price_sans_alerte(self):
        inst = dict(INST_PMP_VIDE, prix_connu=True, prix_fixe_ht=3000)
        kit = composer_kit(**dict(BASE, installation_pompage=inst))
        ligne = next(x for x in kit["inclus"] if x["cle"] == "installation")
        self.assertEqual(ligne["produit"], 60)
        self.assertEqual(ligne["role_pompage"], "installation_pompage")
        self.assertFalse([a for a in kit["alertes"]
                          if a["code"] == "bareme_installation_toiture"])


class Options(unittest.TestCase):

    def test_compteur_coche_sans_produit_price_prix_a_renseigner(self):
        kit = composer_kit(**dict(BASE, options_cochees=["compteur_eau"]))
        option = _option_par_cle(kit, "compteur_eau")
        self.assertTrue(option["cochee"])
        self.assertFalse(option["prix_connu"])
        self.assertIn("prix à renseigner", option["motif"])
        self.assertIn(MENTION_COMPTEUR, option["motif"])
        self.assertNotIn("prix", option)
        ligne = next(x for x in kit["lignes"] if x["cle"] == "compteur_eau")
        self.assertTrue(ligne["designation"].endswith(SUFFIXE_PRIX))
        self.assertIsNone(ligne["produit"])  # jamais un article gratuit
        self.assertIsNone(kit["total_ttc"])

    def test_compteur_non_coche_par_defaut(self):
        self.assertFalse(_option_par_cle(composer_kit(**BASE),
                                         "compteur_eau")["cochee"])

    def test_afficheur_coche_par_defaut_avec_veichi(self):
        kit = composer_kit(**BASE)
        self.assertTrue(_option_par_cle(kit, "afficheur_variateur")["cochee"])
        autre = dict(VARIATEUR, nom="Variateur pompage générique 7,5 kW")
        kit = composer_kit(**dict(BASE, variateur=autre))
        self.assertFalse(_option_par_cle(kit, "afficheur_variateur")["cochee"])

    def test_distance_non_saisie_pas_de_cable_dc(self):
        self.assertNotIn("cable_dc", _cles(composer_kit(**BASE)))
        kit = composer_kit(**dict(BASE, distance_champ_m=25))
        ligne = next(x for x in kit["inclus"] if x["cle"] == "cable_dc")
        self.assertEqual(ligne["quantite"], 25)
        self.assertFalse(ligne["prix_connu"])

    def test_cable_descente_calage_plus_marge_sinon_a_saisir(self):
        kit = composer_kit(**dict(BASE, profondeur_calage_m=60,
                                  marge_cable_m=5))
        self.assertEqual(_option_par_cle(kit, "cable_descente")["quantite"],
                         65)
        kit = composer_kit(**dict(BASE, profondeur_calage_m=60))
        option = _option_par_cle(kit, "cable_descente")
        self.assertIsNone(option["quantite"])
        self.assertIn("marge de câble non réglée", option["motif"])

    def test_option_sans_produit_au_catalogue(self):
        kit = composer_kit(**BASE)
        option = _option_par_cle(kit, "protection_dc")
        self.assertIsNone(option["produit"])
        self.assertIn("aucun produit au catalogue", option["motif"])

    def test_sonde_marche_a_sec_publiee_par_le_variateur(self):
        var = dict(VARIATEUR, fiche={"var_protection_marche_a_sec": True})
        option = _option_par_cle(composer_kit(**dict(BASE, variateur=var)),
                                 "sonde_niveau")
        self.assertIn("protection marche à sec intégrée", option["motif"])

    def test_total_ttc_quand_tout_est_price(self):
        def avec_prix(p, prix):
            return dict(p, prix_ttc=prix)
        pompe = dict(POMPE, prix_ttc=10000)
        inst = dict(INST_PMP_VIDE, prix_connu=True, prix_fixe_ht=3000,
                    prix_ttc=3600)
        kit = composer_kit(**dict(
            BASE, pompe=pompe, variateur=avec_prix(VARIATEUR, 4000),
            panneau=avec_prix(PANNEAU, 1000),
            structure=avec_prix(STRUCTURE, 200), installation_pompage=inst,
            transport=avec_prix(TRANSPORT, 500), options_cochees=[]))
        self.assertEqual(kit["total_ttc"],
                         10000 + 4000 + 14 * 1000 + 14 * 200 + 3600 + 500)


if __name__ == "__main__":
    unittest.main()
