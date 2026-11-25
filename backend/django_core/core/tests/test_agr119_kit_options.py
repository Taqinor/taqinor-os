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
            transport=TRANSPORT, produits_options=OPTIONS_SEED, nb_chaines=1)


def _cles(kit):
    return [ligne["cle"] for ligne in kit["inclus"]]


def _option_par_cle(kit, cle):
    return next(o for o in kit["options"] if o["cle"] == cle)


class KitMinimal(unittest.TestCase):

    def test_kit_neuf_minimal(self):
        kit = composer_kit(**BASE)
        self.assertEqual(_cles(kit), ["pompe", "variateur", "panneaux",
                                      "structure", "coffret_dc",
                                      "disjoncteur_ac", "parafoudre_ac",
                                      "installation", "transport"])
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

    def test_t4v2_004_pose_au_tarif_toiture_dite_en_mots(self):
        # Ni code article ni « alerte interne » : ce qui est chiffré, où le
        # saisir, et le droit qu'il faut.
        kit = composer_kit(**BASE)
        message = next(a["message"] for a in kit["alertes"]
                       if a["code"] == "bareme_installation_toiture")
        self.assertIn("la pose est chiffrée au tarif toiture", message)
        self.assertIn("Stock, article « Installation pompage solaire »",
                      message)
        self.assertIn("Modifier les prix du catalogue", message)
        for interdit in ("INST-PMP", "alerte interne", "Barème toiture"):
            self.assertNotIn(interdit, message)
        sans = composer_kit(**dict(BASE, installation_pompage=None))
        message = next(a["message"] for a in sans["alertes"]
                       if a["code"] == "bareme_installation_toiture")
        self.assertIn("Aucun article de pose du pompage", message)
        self.assertNotIn("INST-PMP", message)

    def test_inst_pmp_price_sans_alerte(self):
        inst = dict(INST_PMP_VIDE, prix_connu=True, prix_fixe_ht=3000)
        kit = composer_kit(**dict(BASE, installation_pompage=inst))
        ligne = next(x for x in kit["inclus"] if x["cle"] == "installation")
        self.assertEqual(ligne["produit"], 60)
        self.assertEqual(ligne["role_pompage"], "installation_pompage")
        self.assertFalse([a for a in kit["alertes"]
                          if a["code"] == "bareme_installation_toiture"])


class Kit(unittest.TestCase):
    """AGQ5 (C-AGQ-004) — barème = prix connu ; socles au kit."""

    def test_installation_a_bareme_est_prix_connu_et_socles_quotes(self):
        inst = dict(INST_PMP_VIDE, prix_fixe_ht=3000, prix_par_panneau_ht=150)
        socle = {"id": 52, "nom": "Socle béton", "prix_connu": True}
        kit = composer_kit(**dict(BASE, installation_pompage=inst,
                                  socle=socle))
        ligne = next(x for x in kit["inclus"] if x["cle"] == "installation")
        self.assertTrue(ligne["prix_connu"])
        self.assertEqual(ligne["produit"], 60)
        self.assertNotIn(SUFFIXE_PRIX, ligne["designation"])
        socles = next(x for x in kit["inclus"] if x["cle"] == "socles")
        self.assertEqual(socles["quantite"], 28)
        self.assertTrue(socles["prix_connu"])
        dans_lignes = next(x for x in kit["lignes"]
                           if x["cle"] == "installation")
        self.assertEqual(dans_lignes["produit"], 60)

    def test_repli_installation_a_bareme_prix_connu(self):
        repli = dict(INST_CAT, prix_connu=False, prix_fixe_ht=2000,
                     prix_par_panneau_ht=250)
        kit = composer_kit(**dict(BASE, installation_toiture=repli))
        ligne = next(x for x in kit["inclus"] if x["cle"] == "installation")
        self.assertTrue(ligne["prix_connu"])
        self.assertEqual(ligne["produit"], 61)


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
        kit = composer_kit(**dict(BASE, produits_options=[
            o for o in OPTIONS_SEED if o["role_pompage"] != "clapet"]))
        option = _option_par_cle(kit, "clapet")
        self.assertIsNone(option["produit"])
        self.assertIn("aucun produit au catalogue", option["motif"])

    def test_sonde_marche_a_sec_publiee_par_le_variateur(self):
        var = dict(VARIATEUR, fiche={"var_protection_marche_a_sec": True})
        option = _option_par_cle(composer_kit(**dict(BASE, variateur=var)),
                                 "sonde_niveau")
        self.assertIn("protection marche à sec intégrée", option["motif"])

    def _marche_a_sec(self, **surcharge):
        kit = composer_kit(**dict(BASE, **surcharge))
        return [a for a in kit["alertes"]
                if a["code"] == "marche_a_sec_non_protegee"]

    def test_acal808_ni_sonde_ni_protection_alerte(self):
        var = dict(VARIATEUR, fiche={"var_protection_marche_a_sec": False})
        alerte = self._marche_a_sec(variateur=var, options_cochees=None)
        self.assertEqual(len(alerte), 1)
        self.assertEqual(set(alerte[0]), {"code", "champ", "message"})
        self.assertEqual(alerte[0]["champ"], "kit.options.sonde_niveau")
        self.assertIn("la pompe tournerait à sec", alerte[0]["message"])

    def test_acal808_protection_inconnue_a_saisir(self):
        var = dict(VARIATEUR, fiche={"var_protection_marche_a_sec": None})
        alerte = self._marche_a_sec(variateur=var)
        self.assertEqual(len(alerte), 1)
        # T4-V2-010 — la phrase dit OÙ saisir l'information manquante.
        self.assertIn("ne dit pas s'il protège la pompe de la marche à sec",
                      alerte[0]["message"])
        self.assertIn("À saisir dans Stock, fiche du variateur",
                      alerte[0]["message"])
        self.assertIn("« %s »" % VARIATEUR["nom"], alerte[0]["message"])

    def test_acal808_sonde_cochee_ou_protection_publiee_aucune_alerte(self):
        sans = dict(VARIATEUR, fiche={"var_protection_marche_a_sec": False})
        self.assertEqual(self._marche_a_sec(
            variateur=sans, options_cochees=["sonde_niveau"]), [])
        avec = dict(VARIATEUR, fiche={"var_protection_marche_a_sec": True})
        self.assertEqual(self._marche_a_sec(variateur=avec), [])
        self.assertEqual(self._marche_a_sec(variateur=None), [])
        placeholder = dict(POMPE, placeholder=True, produit=None)
        self.assertEqual(self._marche_a_sec(variateur=sans, pompe=placeholder),
                         [])

    def test_total_ttc_quand_tout_est_price(self):
        def avec_prix(p, prix):
            return dict(p, prix_ttc=prix)
        pompe = dict(POMPE, prix_ttc=10000)
        inst = dict(INST_PMP_VIDE, prix_connu=True, prix_fixe_ht=3000,
                    prix_ttc=3600)
        protections = [avec_prix(dict(p, prix_connu=True), prix)
                       for p, prix in zip(PROTECTIONS_SEED, (900, 300, 400))]
        kit = composer_kit(**dict(
            BASE, pompe=pompe, variateur=avec_prix(VARIATEUR, 4000),
            panneau=avec_prix(PANNEAU, 1000),
            structure=avec_prix(STRUCTURE, 200), installation_pompage=inst,
            transport=avec_prix(TRANSPORT, 500), options_cochees=[],
            produits_options=OPTIONS_SEED + protections, alimentation="tri",
            courant_pompe_a=10))
        self.assertEqual(kit["total_ttc"],
                         10000 + 4000 + 14 * 1000 + 14 * 200 + 900 + 300
                         + 400 + 3600 + 500)


#: Le lot PVG3 du seeder (``seed_catalogue.CABLES_PROTECTIONS_VIDES``), rôles
#: de ``ROLE_POMPAGE_PVG3`` / migrations 0162 et 0190, prix VIDES.
PROTECTIONS_SEED = [
    _option(90, "Coffret DC 2 strings", "protection_dc"),
    _option(91, "Disjoncteur AC courbe C 16 A tétrapolaire", "protection_ac"),
    _option(92, "Parafoudre AC type 2", "protection_ac"),
]
DISJONCTEURS_SEED = [
    _option(93, "Disjoncteur AC courbe C 16 A monophasé", "protection_ac"),
    _option(94, "Disjoncteur AC courbe C 32 A monophasé", "protection_ac"),
    _option(95, "Disjoncteur AC courbe C 20 A tétrapolaire", "protection_ac"),
    _option(96, "Disjoncteur AC courbe C 32 A tétrapolaire", "protection_ac"),
    _option(97, "Fusible gPV 1000 VDC 15 A", "protection_dc"),
    _option(98, "Sectionneur DC 1000 V 25 A", "protection_dc"),
]


class Protections(unittest.TestCase):
    """D-ACAL-112 / D-ACAL-118 — coffret DC + disjoncteur AC + parafoudre AC
    au kit MINIMUM des nouveaux devis, jamais une option."""

    def _kit(self, **surcharge):
        return composer_kit(**dict(dict(BASE, produits_options=(
            OPTIONS_SEED + PROTECTIONS_SEED + DISJONCTEURS_SEED),
            alimentation="tri"), **surcharge))

    def _ligne(self, kit, cle):
        return next(x for x in kit["inclus"] if x["cle"] == cle)

    def test_plus_une_option_protections(self):
        self.assertNotIn("protection_dc", [o[0] for o in OPTIONS])
        self.assertNotIn("protection_dc",
                         [o["cle"] for o in self._kit()["options"]])

    def test_prix_vides_prix_a_renseigner_jamais_gratuits(self):
        kit = self._kit(courant_pompe_a=14)
        for cle in ("coffret_dc", "disjoncteur_ac", "parafoudre_ac"):
            ligne = self._ligne(kit, cle)
            self.assertIsNotNone(ligne["produit"], cle)
            self.assertFalse(ligne["prix_connu"], cle)
            self.assertTrue(ligne["designation"].endswith(SUFFIXE_PRIX), cle)
            dans_lignes = next(x for x in kit["lignes"] if x["cle"] == cle)
            self.assertIsNone(dans_lignes["produit"])
        self.assertIsNone(kit["total_ttc"])

    def test_coffret_pour_les_chaines_du_champ(self):
        quatre = _option(99, "Coffret DC 4 strings", "protection_dc", True)
        produits = OPTIONS_SEED + PROTECTIONS_SEED + [quatre]
        kit = composer_kit(**dict(BASE, produits_options=produits,
                                  nb_chaines=1))
        self.assertEqual(self._ligne(kit, "coffret_dc")["produit"], 90)
        kit = composer_kit(**dict(BASE, produits_options=produits,
                                  nb_chaines=3))
        self.assertEqual(self._ligne(kit, "coffret_dc")["produit"], 99)
        kit = composer_kit(**dict(BASE, produits_options=produits,
                                  nb_chaines=5))
        ligne = self._ligne(kit, "coffret_dc")
        self.assertIsNone(ligne["produit"])
        self.assertIn("5 chaînes en parallèle", ligne["motif"])

    def test_disjoncteur_de_la_phase_et_du_courant(self):
        kit = self._kit(courant_pompe_a=18)
        self.assertEqual(self._ligne(kit, "disjoncteur_ac")["produit"], 95)
        kit = self._kit(courant_pompe_a=18, alimentation="mono")
        self.assertEqual(self._ligne(kit, "disjoncteur_ac")["produit"], 94)
        kit = self._kit(courant_pompe_a=40)
        ligne = self._ligne(kit, "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("40 A", ligne["motif"])

    def test_calibre_jamais_devine_sans_courant_ni_kw(self):
        ligne = self._ligne(self._kit(), "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("ni kW de la pompe (pompe_kw)", ligne["motif"])
        ligne = self._ligne(self._kit(pompe_kw=5.5), "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("ni tension de la pompe (tension_v)", ligne["motif"])
        # Revue R3 (F2) — UN seul disjoncteur de la phase n'est PAS choisi
        # sans courant (publié ou déduit) : le motif nomme le champ.
        kit = composer_kit(**dict(BASE, produits_options=PROTECTIONS_SEED,
                                  alimentation="tri"))
        ligne = self._ligne(kit, "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("ni kW de la pompe (pompe_kw)", ligne["motif"])
        # Avec un courant : le seul calibre s'il le couvre, sinon aucun.
        kit = composer_kit(**dict(BASE, produits_options=PROTECTIONS_SEED,
                                  alimentation="tri", courant_pompe_a=14))
        self.assertEqual(self._ligne(kit, "disjoncteur_ac")["produit"], 91)
        kit = composer_kit(**dict(BASE, produits_options=PROTECTIONS_SEED,
                                  alimentation="tri", courant_pompe_a=40))
        ligne = self._ligne(kit, "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("courant nominal de la pompe (40 A)", ligne["motif"])

    def test_r3_phase_inconnue_nommee_pas_aucun_article(self):
        kit = composer_kit(**dict(BASE, produits_options=PROTECTIONS_SEED,
                                  courant_pompe_a=14))
        ligne = self._ligne(kit, "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("phase (mono / tri) de la pompe inconnue", ligne["motif"])

    def test_r3_disjoncteur_sans_calibre_publie_jamais_choisi(self):
        sans = [_option(88, "Disjoncteur AC tétrapolaire", "protection_ac")]
        kit = composer_kit(**dict(BASE, produits_options=sans,
                                  alimentation="tri", courant_pompe_a=40))
        ligne = self._ligne(kit, "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("« Disjoncteur AC tétrapolaire » ne publie aucun calibre",
                      ligne["motif"])

    def test_r3_chaines_inconnues_aucun_coffret(self):
        kit = composer_kit(**dict(BASE, produits_options=PROTECTIONS_SEED,
                                  nb_chaines=None))
        ligne = self._ligne(kit, "coffret_dc")
        self.assertIsNone(ligne["produit"])
        self.assertIn("nombre de chaînes en parallèle du champ inconnu",
                      ligne["motif"])
        self.assertIn("fiche du variateur", ligne["motif"])
        motif = ("chaîne PV non vérifiable : fiche du variateur X non saisie")
        kit = composer_kit(**dict(BASE, produits_options=PROTECTIONS_SEED,
                                  nb_chaines=None, motif_chaines=motif))
        self.assertIn(motif, self._ligne(kit, "coffret_dc")["motif"])

    def test_r3_coffret_sans_nombre_de_chaines_jamais_choisi(self):
        sans = [_option(87, "Coffret DC", "protection_dc", True)]
        for n in (1, 3):
            kit = composer_kit(**dict(BASE, produits_options=sans,
                                      nb_chaines=n))
            ligne = self._ligne(kit, "coffret_dc")
            self.assertIsNone(ligne["produit"], n)
            self.assertIn("« Coffret DC » ne publie aucun nombre de chaînes",
                          ligne["motif"])

    def test_dacal124_courant_publie_gagne_sur_le_deduit(self):
        # 15 kW tri 380 V : déduit ≈ 22,8 A ⇒ 32 A ; publié 18 A ⇒ 20 A.
        kit = self._kit(courant_pompe_a=18, pompe_kw=15, tension_pompe_v=380)
        ligne = self._ligne(kit, "disjoncteur_ac")
        self.assertEqual(ligne["produit"], 95)
        self.assertNotIn("hypothese", ligne)
        self.assertFalse([a for a in kit["alertes"]
                          if a["code"] == "calibre_disjoncteur_deduit"])

    def test_dacal124_deduit_triphase(self):
        # I = 15 000 / (√3 × 380) ≈ 22,8 A ⇒ le plus petit tri ≥ : 32 A.
        kit = self._kit(pompe_kw=15, tension_pompe_v=380)
        ligne = self._ligne(kit, "disjoncteur_ac")
        self.assertEqual(ligne["produit"], 96)
        self.assertEqual(
            ligne["hypothese"],
            "Calibre du disjoncteur AC déduit des 15 kW et 380 V de la pompe "
            "(courant estimé 22,8 A, sans facteur de puissance ni rendement "
            "du moteur : sous-estimé) ; saisir le courant nominal de la pompe "
            "sur sa fiche du catalogue le remplace.")
        alerte = [a for a in kit["alertes"]
                  if a["code"] == "calibre_disjoncteur_deduit"]
        self.assertEqual(len(alerte), 1)
        self.assertTrue(alerte[0]["interne"])
        self.assertEqual(alerte[0]["champ"], "kit.disjoncteur_ac")

    def test_dacal124_deduit_monophase(self):
        # I = 3 000 / 220 ≈ 13,6 A ⇒ le plus petit mono ≥ : 16 A ;
        # 5 kW ⇒ 22,7 A ⇒ 32 A.
        kit = self._kit(alimentation="mono", pompe_kw=3, tension_pompe_v=220)
        self.assertEqual(self._ligne(kit, "disjoncteur_ac")["produit"], 93)
        kit = self._kit(alimentation="mono", pompe_kw=5, tension_pompe_v=220)
        self.assertEqual(self._ligne(kit, "disjoncteur_ac")["produit"], 94)

    def test_dacal124_deduit_trop_fort_motif_estime(self):
        ligne = self._ligne(self._kit(pompe_kw=30, tension_pompe_v=380),
                            "disjoncteur_ac")
        self.assertIsNone(ligne["produit"])
        self.assertIn("courant estimé de la pompe (45,6 A)", ligne["motif"])

    def test_jamais_un_fusible_ni_un_sectionneur_pour_coffret(self):
        kit = composer_kit(**dict(BASE, produits_options=DISJONCTEURS_SEED))
        ligne = self._ligne(kit, "coffret_dc")
        self.assertIsNone(ligne["produit"])
        self.assertTrue(ligne["designation"].startswith(
            "Coffret de protection DC"))

    def test_sans_champ_ni_variateur_pas_de_protection(self):
        kit = self._kit(nb_panneaux=None, variateur=None)
        for cle in ("coffret_dc", "disjoncteur_ac", "parafoudre_ac"):
            self.assertNotIn(cle, _cles(kit))

    def test_zero_batterie_zero_onduleur_avec_protections(self):
        for ligne in self._kit(courant_pompe_a=14)["inclus"]:
            texte = (ligne["designation"] or "").lower()
            self.assertNotIn("batterie", texte)
            self.assertNotIn("onduleur", texte)


if __name__ == "__main__":
    unittest.main()
