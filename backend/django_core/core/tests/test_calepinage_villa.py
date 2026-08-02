# -*- coding: utf-8 -*-
"""AOF162 — adaptateur VILLA : goldens figés, inversion lat/lng, apps/web intact."""

import io
import json
import os
import unittest

from core.calepinage.adaptateurs.villa import (
    DEGAGEMENT_VILLA_M,
    RETRAIT_VILLA_M,
    Projection,
    expliquer_ecart,
    politique_villa,
    projection_locale,
    vers_entree,
    vers_panneaux,
)
from core.calepinage.garde_fous import valider
from core.calepinage.perf import optimiser_economique
from core.calepinage.politique_pas import Affleurant, AntiOmbrage
from core.calepinage.poseur import poser_plan
from core.calepinage.types import KIT_VILLA_720, Axe, Provenance

PAQUET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calepinage")
GOLDEN = os.path.join(PAQUET, "golden", "villa")

#: comptes de RÉFÉRENCE du moteur sur les toitures villa FIGÉES
ATTENDUS_VILLA = (
    ("villa_plate_14x10.json", "ANTI_OMBRAGE", 18),
    ("villa_pente_12x8.json", "AFFLEURANT", 24),
)


def _charger(nom):
    with io.open(os.path.join(GOLDEN, nom), encoding="utf-8") as fh:
        return json.load(fh)


def _calepiner(area, ordre="lnglat"):
    entree, projection, politique = vers_entree(area, ordre)
    resultat = optimiser_economique(entree.surfaces[0], entree.parametres,
                                    entree.obstacles, entree.zones, politique)
    return entree, projection, politique, resultat


class LesGoldensVillaSontFiges(unittest.TestCase):
    def test_les_fichiers_existent(self):
        for nom, _politique, _modules in ATTENDUS_VILLA:
            self.assertTrue(os.path.exists(os.path.join(GOLDEN, nom)), nom)

    def test_chaque_toiture_redonne_son_compte(self):
        for nom, code_politique, modules in ATTENDUS_VILLA:
            _e, _p, politique, resultat = _calepiner(_charger(nom))
            self.assertEqual(politique.code, code_politique, nom)
            self.assertEqual(resultat.modules, modules, nom)

    def test_le_poseur_et_le_compteur_s_accordent_sur_la_villa(self):
        for nom, _code, modules in ATTENDUS_VILLA:
            entree, _proj, _pol, resultat = _calepiner(_charger(nom))
            kit = entree.parametres.kits[0]
            tables = poser_plan(entree.surfaces[0],
                                tuple((y, kit) for y, _c in resultat.rangees),
                                entree.obstacles)
            self.assertEqual(len(tables) * kit.modules_par_pas, modules, nom)

    def test_le_plan_villa_passe_les_garde_fous(self):
        entree, _proj, _pol, resultat = _calepiner(
            _charger("villa_plate_14x10.json"))
        kit = entree.parametres.kits[0]
        rapport = valider(entree.surfaces[0], entree.parametres,
                          tuple((y, kit) for y, _c in resultat.rangees),
                          entree.obstacles, strict=False)
        self.assertTrue(rapport.ok, rapport.echecs)


class LeKitEtLesReglesVilla(unittest.TestCase):
    def test_le_kit_est_a_un_module_720_wc(self):
        entree, _p, _pol, _r = _calepiner(_charger("villa_plate_14x10.json"))
        kit = entree.parametres.kits[0]
        self.assertIs(kit, KIT_VILLA_720)
        self.assertEqual(kit.modules_par_table, 1)
        self.assertAlmostEqual(kit.puissance_module_wc, 720.0)
        self.assertAlmostEqual(kit.inclinaison_deg, 13.0)

    def test_le_retrait_de_rive_villa_est_de_50_cm(self):
        entree, _p, _pol, _r = _calepiner(_charger("villa_plate_14x10.json"))
        self.assertAlmostEqual(entree.parametres.rives.laterale_m,
                               RETRAIT_VILLA_M)
        self.assertAlmostEqual(entree.surfaces[0].rives.extremite_m,
                               RETRAIT_VILLA_M)

    def test_les_obstacles_sont_declares_par_le_client(self):
        entree, _p, _pol, _r = _calepiner(_charger("villa_plate_14x10.json"))
        self.assertEqual(len(entree.obstacles), 1)
        obstacle = entree.obstacles[0]
        self.assertIs(obstacle.provenance, Provenance.DECLARE_CLIENT)
        self.assertAlmostEqual(obstacle.degagement_m, DEGAGEMENT_VILLA_M)
        self.assertAlmostEqual(obstacle.x1 - obstacle.x0, 1.2, delta=0.01)
        self.assertAlmostEqual(obstacle.y1 - obstacle.y0, 1.0, delta=0.01)

    def test_les_rangees_villa_courent_est_ouest(self):
        entree, _p, _pol, _r = _calepiner(_charger("villa_plate_14x10.json"))
        self.assertIs(entree.parametres.axe_rangee, Axe.EST_OUEST)
        self.assertIs(entree.surfaces[0].axe_rangee, Axe.EST_OUEST)

    def test_toit_plat_anti_ombrage_toit_en_pente_affleurant(self):
        self.assertIsInstance(politique_villa({"flat": True, "tilt": 0.0}),
                              AntiOmbrage)
        self.assertIsInstance(politique_villa({"flat": False, "tilt": 13.0}),
                              Affleurant)

    def test_un_contour_trop_court_est_refuse(self):
        with self.assertRaises(ValueError):
            vers_entree({"id": "X", "polygon": [[0, 0], [1, 1]]})


class LInversionLatLngEstCouverte(unittest.TestCase):
    """Test DÉDIÉ : le lecteur de cartes sérialise [lng, lat], le CRM [lat, lng]."""

    def test_les_deux_ordres_donnent_la_meme_toiture(self):
        area = _charger("villa_plate_14x10.json")
        inverse = dict(area)
        inverse["polygon"] = [[p[1], p[0]] for p in area["polygon"]]
        inverse["obstacles"] = [dict(o, center=[o["center"][1],
                                                o["center"][0]])
                                for o in area["obstacles"]]
        droit = _calepiner(area, "lnglat")[3]
        retourne = _calepiner(inverse, "latlng")[3]
        self.assertEqual(droit.modules, retourne.modules)

    def test_lire_un_contour_a_l_envers_donne_une_toiture_fausse(self):
        area = _charger("villa_plate_14x10.json")
        _e, _p, _pol, droit = _calepiner(area, "lnglat")
        _e2, _p2, _pol2, faux = _calepiner(area, "latlng")
        self.assertNotEqual(droit.modules, faux.modules)

    def test_un_ordre_inconnu_leve(self):
        with self.assertRaises(ValueError):
            vers_entree(_charger("villa_plate_14x10.json"), ordre="xy")


class ProjectionLocale(unittest.TestCase):
    def test_aller_retour_de_projection(self):
        projection = Projection(lat0_deg=33.686, lng0_deg=-7.383)
        lat, lng = projection.vers_geo(12.0, -8.0)
        est, nord = projection.vers_local(lat, lng)
        self.assertAlmostEqual(est, 12.0, delta=1e-6)
        self.assertAlmostEqual(nord, -8.0, delta=1e-6)

    def test_la_projection_est_ancree_sur_le_barycentre(self):
        area = _charger("villa_plate_14x10.json")
        projection = projection_locale(area["polygon"])
        self.assertAlmostEqual(projection.lat0_deg, 33.686, delta=1e-6)
        self.assertAlmostEqual(projection.lng0_deg, -7.383, delta=1e-6)

    def test_le_contour_projete_a_les_bonnes_dimensions(self):
        entree, _p, _pol, _r = _calepiner(_charger("villa_plate_14x10.json"))
        contour = entree.surfaces[0].contour
        largeur = max(p[0] for p in contour) - min(p[0] for p in contour)
        hauteur = max(p[1] for p in contour) - min(p[1] for p in contour)
        self.assertAlmostEqual(largeur, 14.0, delta=0.01)
        self.assertAlmostEqual(hauteur, 10.0, delta=0.01)


class SortieCompatibleEcran(unittest.TestCase):
    def test_les_panneaux_reviennent_en_lng_lat(self):
        entree, projection, _pol, resultat = _calepiner(
            _charger("villa_plate_14x10.json"))
        kit = entree.parametres.kits[0]
        tables = poser_plan(entree.surfaces[0],
                            tuple((y, kit) for y, _c in resultat.rangees),
                            entree.obstacles)
        panneaux = vers_panneaux(tables, projection)
        self.assertEqual(len(panneaux), resultat.modules)
        premier = panneaux[0]
        self.assertEqual(len(premier["corners"]), 4)
        lng, lat = premier["corners"][0]
        self.assertAlmostEqual(lat, 33.686, delta=0.001)
        self.assertAlmostEqual(lng, -7.383, delta=0.001)
        self.assertAlmostEqual(premier["wc"], 720.0)


class EcartExpliqueObstacleParObstacle(unittest.TestCase):
    def test_un_ecart_couvert_est_declare_explique(self):
        ok, lignes = expliquer_ecart(None, 20, 18,
                                     impacts=(("EDICULE", 2),))
        self.assertTrue(ok)
        self.assertIn("EDICULE", lignes[1])
        self.assertIn("intégralement expliqué", lignes[-1])

    def test_un_ecart_non_couvert_est_nomme(self):
        ok, lignes = expliquer_ecart(None, 24, 18, impacts=(("EDICULE", 2),))
        self.assertFalse(ok)
        self.assertIn("RESTE NON EXPLIQUÉ", lignes[-1])


class AppsWebResteIntact(unittest.TestCase):
    """Le cerveau TypeScript n'est ni touché ni importé (règle de run)."""

    def test_le_moteur_ne_reference_jamais_apps_web(self):
        fautifs = []
        for racine, _dirs, fichiers in os.walk(PAQUET):
            for nom in fichiers:
                if not nom.endswith(".py"):
                    continue
                chemin = os.path.join(racine, nom)
                with io.open(chemin, encoding="utf-8") as fh:
                    contenu = fh.read()
                if "apps/web" in contenu.replace(
                        "``apps/web`` n'est PAS modifié", ""):
                    fautifs.append(os.path.relpath(chemin, PAQUET))
        self.assertEqual(fautifs, [],
                         "le noyau ne doit jamais viser apps/web : %r"
                         % (fautifs,))

    def test_aucun_import_du_cerveau_typescript(self):
        for racine, _dirs, fichiers in os.walk(PAQUET):
            for nom in fichiers:
                if not nom.endswith(".py"):
                    continue
                with io.open(os.path.join(racine, nom), encoding="utf-8") as fh:
                    contenu = fh.read()
                for interdit in ("roofPro2", "estimatorBrainV2", "roofPro11/"):
                    self.assertNotIn(interdit + "(", contenu)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
