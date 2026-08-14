# -*- coding: utf-8 -*-
"""PV66 — la villa sait enfin poser un CHEVRON dos-à-dos est-ouest.

Jusqu'ici une villa n'avait qu'une seule façon d'être couverte : un module par
table, plein sud. Le lecteur de cartes du site, lui, compare depuis longtemps
DEUX familles (``ConfigFamily = 'south' | 'eastwest'``) et l'est-ouest loge
nettement plus de panneaux sur une toiture plate. L'ERP chiffrait donc une
toiture avec une seule des deux réponses, et jamais la plus dense.

Ce module prouve quatre choses, et rien d'autre :

  1. **Le chevron existe comme un simple ``Kit``** — deux modules dos-à-dos,
     faîtage nord-sud, aucun champ neuf dans le contrat gelé de ``types.py`` ;
  2. **Les deux familles ne rendent pas le même compte** sur LA MÊME toiture,
     et l'écart est produit par le moteur, jamais estimé ;
  3. **Le défaut ne bouge pas d'un bit** — sans famille demandée, le calcul est
     exactement celui d'avant PV66 (goldens villa compris) ;
  4. **Le panneau du catalogue (PV12) s'applique aux deux familles** — choisir
     l'est-ouest change la TABLE, jamais le module facturé.

Run :
    python manage.py test core.tests.test_calepinage_villa_ew -v2
"""

import io
import json
import math
import os
import unittest

from core.calepinage.adaptateurs.villa import (
    FAMILLE_EST_OUEST,
    FAMILLE_SUD,
    kit_de_famille,
    kit_est_ouest,
    kit_sud,
    vers_entree,
    vers_panneaux,
)
from core.calepinage.garde_fous import valider
from core.calepinage.optimum import optimiser
from core.calepinage.orientation import ErreurOrientation, verifier_kit
from core.calepinage.perf import optimiser_economique
from core.calepinage.poseur import poser_plan
from core.calepinage.adaptateurs.villa import Projection
from core.calepinage.types import (
    KIT_VILLA_720,
    KIT_VILLA_EW,
    Axe,
    OrientationModule,
    remplacer,
)

PAQUET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calepinage")
GOLDEN = os.path.join(PAQUET, "golden", "villa")

#: La toiture PLATE figée du golden villa : 14 m est-ouest × 10 m nord-sud,
#: avec un édicule au nord-est.
TOITURE = "villa_plate_14x10.json"

#: Ancre géographique (Mohammedia) — sans portée métier : elle ne sert qu'à
#: l'aller-retour mètres -> degrés du lecteur de cartes.
LAT0, LNG0 = 33.686, -7.383
#: Toiture d'essai LIBRE : 14 m est-ouest × 10 m nord-sud, AUCUN obstacle.
DEMI_LARGEUR_M, DEMI_HAUTEUR_M = 7.0, 5.0


def _charger(nom):
    with io.open(os.path.join(GOLDEN, nom), encoding="utf-8") as fh:
        return json.load(fh)


def _toiture_libre():
    """Le même rectangle que le golden, mais SANS édicule.

    Le golden porte un édicule qui coupe la bande transversale : il fait perdre
    une rangée à l'est-ouest et les deux familles s'y égalisent par accident
    (18 = 18). Comparer les deux poses demande donc une toiture LIBRE — sinon
    le test mesurerait l'obstacle, pas la famille.
    """
    projection = Projection(lat0_deg=LAT0, lng0_deg=LNG0)
    points = []
    for est, nord in ((-DEMI_LARGEUR_M, -DEMI_HAUTEUR_M),
                      (DEMI_LARGEUR_M, -DEMI_HAUTEUR_M),
                      (DEMI_LARGEUR_M, DEMI_HAUTEUR_M),
                      (-DEMI_LARGEUR_M, DEMI_HAUTEUR_M)):
        lat, lng = projection.vers_geo(est, nord)
        points.append([lng, lat])
    return {"id": "VILLA_LIBRE_14x10", "polygon": points, "flat": True,
            "tilt": 0.0, "azimuth": 180.0, "obstacles": []}


def _calepiner(area, famille=None, kit=KIT_VILLA_720):
    """Pose la toiture avec la famille demandée et rend ``(entrée, résultat)``."""
    entree, projection, politique = vers_entree(area, kit=kit, famille=famille)
    resultat = optimiser_economique(entree.surfaces[0], entree.parametres,
                                    entree.obstacles, entree.zones, politique)
    return entree, projection, politique, resultat


class LeChevronEstUnKitCommeLesAutres(unittest.TestCase):
    """PV66-1 — aucune structure neuve : deux modules par table suffisent."""

    def test_le_chevron_porte_deux_modules_du_meme_format_que_la_villa(self):
        self.assertEqual(KIT_VILLA_EW.modules_par_table, 2)
        self.assertTrue(KIT_VILLA_EW.dos_a_dos)
        self.assertAlmostEqual(KIT_VILLA_EW.module_long_m,
                               KIT_VILLA_720.module_long_m)
        self.assertAlmostEqual(KIT_VILLA_EW.module_court_m,
                               KIT_VILLA_720.module_court_m)
        self.assertAlmostEqual(KIT_VILLA_EW.puissance_module_wc,
                               KIT_VILLA_720.puissance_module_wc)

    def test_l_inclinaison_du_chevron_reste_faible(self):
        """Le site ne balaie que 10° et 15° en est-ouest : on tient la borne."""
        self.assertGreaterEqual(KIT_VILLA_EW.inclinaison_deg, 10.0)
        self.assertLessEqual(KIT_VILLA_EW.inclinaison_deg, 12.0)

    def test_le_faitage_court_nord_sud_donc_les_rangees_aussi(self):
        self.assertIs(KIT_VILLA_EW.axe_faitage, Axe.NORD_SUD)
        self.assertIs(verifier_kit(KIT_VILLA_EW, Axe.NORD_SUD), Axe.NORD_SUD)
        with self.assertRaises(ErreurOrientation):
            verifier_kit(KIT_VILLA_EW, Axe.EST_OUEST)

    def test_l_emprise_vaut_deux_empreintes_sans_jeu_de_faite(self):
        """``2 × empreinte`` exactement, comme la cellule E-O du site."""
        empreinte = (KIT_VILLA_EW.cote_dans_la_pente_m
                     * math.cos(math.radians(KIT_VILLA_EW.inclinaison_deg)))
        self.assertAlmostEqual(KIT_VILLA_EW.faitage_m, 0.0)
        self.assertAlmostEqual(KIT_VILLA_EW.emprise_transversale_m,
                               2.0 * empreinte, places=9)

    def test_le_chevron_est_en_paysage_donc_le_moins_profond(self):
        self.assertIs(KIT_VILLA_EW.orientation, OrientationModule.PAYSAGE)
        self.assertAlmostEqual(KIT_VILLA_EW.cote_le_long_rangee_m, 2.384)
        self.assertAlmostEqual(KIT_VILLA_EW.cote_dans_la_pente_m, 1.303)

    def test_une_table_de_chevron_pese_deux_modules(self):
        self.assertAlmostEqual(KIT_VILLA_EW.puissance_table_wc, 1440.0)
        self.assertEqual(KIT_VILLA_EW.modules_par_pas, 2)


class LesDeuxFamillesNeRendentPasLeMemeCompte(unittest.TestCase):
    """PV66-2 — l'écart est CALCULÉ par le moteur, jamais annoncé d'avance."""

    def setUp(self):
        self.area = _toiture_libre()

    def test_l_est_ouest_change_le_compte(self):
        _e, _p, _pol, sud = _calepiner(self.area, FAMILLE_SUD)
        _e2, _p2, _pol2, ew = _calepiner(self.area, FAMILLE_EST_OUEST)
        self.assertGreater(sud.modules, 0)
        self.assertGreater(ew.modules, 0)
        self.assertNotEqual(sud.modules, ew.modules)

    def test_sur_cette_toiture_libre_l_est_ouest_en_loge_davantage(self):
        """14 × 10 m plate et nue : 18 en plein sud, 24 en chevron est-ouest."""
        _e, _p, _pol, sud = _calepiner(self.area, FAMILLE_SUD)
        _e2, _p2, _pol2, ew = _calepiner(self.area, FAMILLE_EST_OUEST)
        self.assertEqual(sud.modules, 18)
        self.assertEqual(ew.modules, 24)

    def test_l_edicule_du_golden_coute_un_chevron_a_l_est_ouest(self):
        """Le golden porte un édicule : l'est-ouest y perd un chevron (24 -> 22).

        Le plein sud, lui, ne perd rien (18) : l'édicule tombe entre deux de
        ses rangées. L'écart entre familles est donc une propriété de CETTE
        toiture, recalculée à chaque fois, jamais un ratio appris.
        """
        golden = _charger(TOITURE)
        _e, _p, _pol, sud = _calepiner(golden, FAMILLE_SUD)
        _e2, _p2, _pol2, ew = _calepiner(golden, FAMILLE_EST_OUEST)
        self.assertEqual(sud.modules, 18)
        self.assertEqual(ew.modules, 22)

    def test_le_jeu_de_positions_economique_ne_perd_aucun_module(self):
        """PV66 a corrigé ``positions_utiles`` : il chaînait avec ``allee_m``.

        La villa pose ``allee_m = 0`` et confie l'espacement à ``AntiOmbrage``.
        La fermeture rendait donc un jeu de positions plus pauvre que la
        grille au centimètre — et publiait 18 modules là où le moteur exact en
        pose 24. « Même résultat, moins cher » doit être un FAIT.
        """
        for famille in (FAMILLE_SUD, FAMILLE_EST_OUEST):
            entree, _p, politique, economique = _calepiner(self.area, famille)
            exact = optimiser(entree.surfaces[0], entree.parametres,
                              entree.obstacles, entree.zones, politique)
            self.assertEqual(economique.modules, exact.modules, famille)

    def test_l_est_ouest_pose_un_nombre_pair_de_modules(self):
        """Deux modules par table : un chevron ne se coupe pas en deux."""
        _e, _p, _pol, ew = _calepiner(self.area, FAMILLE_EST_OUEST)
        self.assertEqual(ew.modules % 2, 0)

    def test_les_rangees_est_ouest_courent_nord_sud(self):
        entree, _p, _pol, _r = _calepiner(self.area, FAMILLE_EST_OUEST)
        self.assertIs(entree.parametres.axe_rangee, Axe.NORD_SUD)
        self.assertIs(entree.surfaces[0].axe_rangee, Axe.NORD_SUD)

    def test_le_contour_est_transpose_avec_l_axe(self):
        """14 m est-ouest × 10 m nord-sud : en rangées nord-sud, x mesure 10."""
        sud, _p, _pol, _r = _calepiner(self.area, FAMILLE_SUD)
        ew, _p2, _pol2, _r2 = _calepiner(self.area, FAMILLE_EST_OUEST)
        etendue = lambda c, i: (max(p[i] for p in c) - min(p[i] for p in c))  # noqa: E731
        self.assertAlmostEqual(etendue(sud.surfaces[0].contour, 0),
                               etendue(ew.surfaces[0].contour, 1), places=6)
        self.assertAlmostEqual(etendue(sud.surfaces[0].contour, 1),
                               etendue(ew.surfaces[0].contour, 0), places=6)

    def test_le_plan_est_ouest_passe_les_garde_fous(self):
        entree, _p, _pol, resultat = _calepiner(self.area, FAMILLE_EST_OUEST)
        kit = entree.parametres.kits[0]
        rapport = valider(entree.surfaces[0], entree.parametres,
                          tuple((y, kit) for y, _c in resultat.rangees),
                          entree.obstacles, strict=False)
        self.assertTrue(rapport.ok, rapport.echecs)

    def test_le_poseur_et_le_compteur_s_accordent_sur_le_chevron(self):
        entree, _p, _pol, resultat = _calepiner(self.area, FAMILLE_EST_OUEST)
        kit = entree.parametres.kits[0]
        tables = poser_plan(entree.surfaces[0],
                            tuple((y, kit) for y, _c in resultat.rangees),
                            entree.obstacles)
        self.assertEqual(len(tables) * kit.modules_par_pas, resultat.modules)

    def test_les_panneaux_rendus_reviennent_sur_la_toiture(self):
        """La transposition se DÉFAIT au rendu : sinon le chevron part à 90°."""
        entree, projection, _pol, resultat = _calepiner(
            self.area, FAMILLE_EST_OUEST)
        kit = entree.parametres.kits[0]
        tables = poser_plan(entree.surfaces[0],
                            tuple((y, kit) for y, _c in resultat.rangees),
                            entree.obstacles)
        panneaux = vers_panneaux(tables, projection, kit,
                                 entree.parametres.axe_rangee)
        self.assertTrue(panneaux)
        contour = [projection.vers_geo(*_p) for _p in
                   ((-7.0, -5.0), (7.0, 5.0))]
        lat_min, lat_max = contour[0][0], contour[1][0]
        lng_min, lng_max = contour[0][1], contour[1][1]
        for panneau in panneaux:
            for lng, lat in panneau["corners"]:
                self.assertGreaterEqual(lat, lat_min - 1e-6)
                self.assertLessEqual(lat, lat_max + 1e-6)
                self.assertGreaterEqual(lng, lng_min - 1e-6)
                self.assertLessEqual(lng, lng_max + 1e-6)


class LeDefautNeBougePasDUnBit(unittest.TestCase):
    """PV66-3 — non-régression : sans famille demandée, rien ne change."""

    def test_sans_famille_le_kit_recu_traverse_intact(self):
        entree, _p, _pol, _r = _calepiner(_charger(TOITURE))
        self.assertIs(entree.parametres.kits[0], KIT_VILLA_720)
        self.assertIs(entree.parametres.axe_rangee, Axe.EST_OUEST)
        self.assertIs(entree.surfaces[0].axe_rangee, Axe.EST_OUEST)

    def test_sans_famille_le_compte_est_celui_de_la_famille_sud(self):
        _e, _p, _pol, defaut = _calepiner(_charger(TOITURE))
        _e2, _p2, _pol2, sud = _calepiner(_charger(TOITURE), FAMILLE_SUD)
        self.assertEqual(defaut.modules, sud.modules)

    def test_le_golden_villa_plat_rend_toujours_18_modules(self):
        _e, _p, _pol, defaut = _calepiner(_charger(TOITURE))
        self.assertEqual(defaut.modules, 18)

    def test_le_golden_villa_en_pente_rend_toujours_24_modules(self):
        _e, _p, _pol, defaut = _calepiner(_charger("villa_pente_12x8.json"))
        self.assertEqual(defaut.modules, 24)

    def test_une_famille_inconnue_est_refusee_jamais_devinee(self):
        with self.assertRaises(ValueError):
            kit_de_famille("plein_ouest")
        with self.assertRaises(ValueError):
            vers_entree(_charger(TOITURE), famille="chevron")


class LePanneauDuCatalogueSApplique(unittest.TestCase):
    """PV66-4 — PV12 se compose : la famille change la table, pas le module."""

    #: Un 450 Wc plus petit — la géométrie d'une fiche technique quelconque.
    AUTRE = remplacer(KIT_VILLA_720, code="SKU450", libelle="Panneau 450 Wc",
                      module_long_m=1.9, module_court_m=1.1,
                      puissance_module_wc=450.0)

    def test_le_chevron_herite_des_dimensions_du_produit(self):
        chevron = kit_est_ouest(self.AUTRE)
        self.assertAlmostEqual(chevron.module_long_m, 1.9)
        self.assertAlmostEqual(chevron.module_court_m, 1.1)
        self.assertAlmostEqual(chevron.puissance_module_wc, 450.0)
        self.assertEqual(chevron.modules_par_table, 2)
        self.assertAlmostEqual(chevron.inclinaison_deg,
                               KIT_VILLA_EW.inclinaison_deg)
        self.assertIn(self.AUTRE.code, chevron.code)

    def test_le_kit_villa_de_reference_donne_le_chevron_de_reference(self):
        self.assertIs(kit_est_ouest(KIT_VILLA_720), KIT_VILLA_EW)

    def test_un_chevron_reste_un_chevron(self):
        self.assertIs(kit_est_ouest(KIT_VILLA_EW), KIT_VILLA_EW)
        self.assertIs(kit_de_famille(FAMILLE_EST_OUEST, KIT_VILLA_EW),
                      KIT_VILLA_EW)

    def test_la_famille_sud_laisse_un_kit_a_un_module_intact(self):
        self.assertIs(kit_sud(self.AUTRE), self.AUTRE)
        self.assertIs(kit_de_famille(FAMILLE_SUD, self.AUTRE), self.AUTRE)

    def test_la_famille_sud_redescend_un_chevron_a_un_module(self):
        sud = kit_sud(KIT_VILLA_EW)
        self.assertEqual(sud.modules_par_table, 1)
        self.assertFalse(sud.dos_a_dos)
        self.assertAlmostEqual(sud.puissance_module_wc,
                               KIT_VILLA_EW.puissance_module_wc)

    def test_le_produit_traverse_les_deux_familles_sur_la_toiture(self):
        area = _toiture_libre()
        _e, _p, _pol, sud = _calepiner(area, FAMILLE_SUD, kit=self.AUTRE)
        entree, _p2, _pol2, ew = _calepiner(area, FAMILLE_EST_OUEST,
                                            kit=self.AUTRE)
        self.assertNotEqual(sud.modules, ew.modules)
        self.assertAlmostEqual(entree.parametres.kits[0].puissance_module_wc,
                               450.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
