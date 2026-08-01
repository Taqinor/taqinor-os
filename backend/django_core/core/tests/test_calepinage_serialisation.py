# -*- coding: utf-8 -*-
"""AOF57 — schéma JSON versionné + hash d'entrée au MILLIMÈTRE.

Les trois jeux FRDISI font l'aller-retour JSON sans perte : rectangle (école),
polygone (aile en L) et arc (bâtiment B).
"""

import json
import os
import unittest

from core.calepinage.obstacles import appliquer_regles
from core.calepinage.optimum import optimiser
from core.calepinage.serialisation import (
    EntreeCalepinage,
    ResultatCalepinage,
    SchemaIncompatible,
    hash_entree,
    migrer,
    surface_depuis_dict,
    surface_vers_dict,
)
from core.calepinage.surfaces.arc import arc_frdisi
from core.calepinage.surfaces.multi import Palier, SurfaceMultiNiveaux
from core.calepinage.surfaces.rectangle import SurfaceRectangle
from core.calepinage.types import (
    KIT_AO_PAYSAGE,
    KIT_AO_PORTRAIT,
    NatureZone,
    Parametres,
    Rives,
    Zone,
    remplacer,
)
from core.calepinage.version import SCHEMA_VERSION, VERSION_MOTEUR
from core.tests.test_calepinage_moteur import ECOLE_OBSTACLES
from core.tests.test_calepinage_optimum import (
    RIVES_AO,
    obstacles_aile_l,
    surface_aile_l,
)
from core.tests.test_calepinage_pose_uniforme import obstacles_arc


def _parametres(kits=(KIT_AO_PORTRAIT,)):
    return Parametres(kits=kits, rives=RIVES_AO, allee_m=0.60,
                      pas_recherche_m=0.01, engagement_modules=152)


def _entree_ecole():
    return EntreeCalepinage(
        repere="BAT_C_ECOLE",
        surfaces=(SurfaceRectangle(repere="BAT_C_ECOLE", longueur_m=51.10,
                                   largeur_m=25.62, rives=RIVES_AO),),
        kits=(KIT_AO_PORTRAIT,), parametres=_parametres(),
        obstacles=appliquer_regles(ECOLE_OBSTACLES),
        engagements=(("BAT_C_ECOLE", 288),))


def _entree_aile_l():
    return EntreeCalepinage(
        repere="BAT_A_AILE_L", surfaces=(surface_aile_l(),),
        kits=(KIT_AO_PORTRAIT, KIT_AO_PAYSAGE),
        parametres=_parametres((KIT_AO_PORTRAIT, KIT_AO_PAYSAGE)),
        obstacles=obstacles_aile_l(), engagements=(("BAT_A_AILE_L", 152),))


def _entree_arc():
    return EntreeCalepinage(
        repere="BAT_B_ARC", surfaces=(arc_frdisi(rives=RIVES_AO),),
        kits=(KIT_AO_PAYSAGE,), parametres=_parametres((KIT_AO_PAYSAGE,)),
        obstacles=obstacles_arc("S2"), engagements=(("BAT_B_ARC", 120),))


class AllerRetourSansPerte(unittest.TestCase):
    """Les 3 jeux FRDISI : rectangle, polygone, arc."""

    def _tour(self, entree):
        refaite = EntreeCalepinage.depuis_json(entree.vers_json())
        self.assertEqual(refaite.vers_dict(), entree.vers_dict())
        self.assertEqual(refaite.hash_entree, entree.hash_entree)
        return refaite

    def test_ecole(self):
        refaite = self._tour(_entree_ecole())
        self.assertEqual(refaite.surfaces[0].repere, "BAT_C_ECOLE")
        self.assertEqual(len(refaite.obstacles), 5)

    def test_aile_l(self):
        refaite = self._tour(_entree_aile_l())
        self.assertEqual(len(refaite.surfaces[0].contour), 6)
        self.assertEqual(len(refaite.obstacles), 30)

    def test_arc(self):
        refaite = self._tour(_entree_arc())
        self.assertAlmostEqual(refaite.surfaces[0].rayon_ext_m, 274.0)
        self.assertEqual(len(refaite.surfaces[0].coupures()), 2)

    def test_le_compte_survit_a_l_aller_retour(self):
        entree = _entree_ecole()
        refaite = EntreeCalepinage.depuis_json(entree.vers_json())
        avant = optimiser(entree.surfaces[0], entree.parametres,
                          entree.obstacles)
        apres = optimiser(refaite.surfaces[0], refaite.parametres,
                          refaite.obstacles)
        self.assertEqual(avant.modules, apres.modules)
        self.assertEqual(avant.modules, 314)

    def test_les_zones_survivent(self):
        zone = Zone(repere="SERVITUDE", nature=NatureZone.INTERDITE,
                    sommets=((0.0, 0.0), (5.0, 0.0), (5.0, 3.0)),
                    retrait_m=0.20)
        entree = remplacer(_entree_ecole(), zones=(zone,))
        refaite = EntreeCalepinage.depuis_json(entree.vers_json())
        self.assertEqual(refaite.zones[0].nature, NatureZone.INTERDITE)
        self.assertAlmostEqual(refaite.zones[0].retrait_m, 0.20)

    def test_une_surface_multi_niveaux_survit(self):
        surface = SurfaceMultiNiveaux(
            repere="ECOLE", largeur_m=25.62, rives=RIVES_AO,
            paliers=(Palier(repere="BAS", x0=0.0, x1=31.74, niveau=0),
                     Palier(repere="HAUT", x0=31.74, x1=51.10, niveau=1)))
        refaite = surface_depuis_dict(surface_vers_dict(surface))
        self.assertEqual(refaite.niveaux, (0, 1))
        self.assertEqual(len(refaite.paliers), 2)


class HashAuMillimetre(unittest.TestCase):
    def test_le_hash_est_stable(self):
        self.assertEqual(_entree_ecole().hash_entree,
                         _entree_ecole().hash_entree)

    def test_un_deplacement_inferieur_au_millimetre_ne_change_pas_le_hash(self):
        entree = _entree_ecole()
        bougee = remplacer(entree, surfaces=(
            remplacer(entree.surfaces[0], longueur_m=51.1004),))
        self.assertEqual(bougee.hash_entree, entree.hash_entree)

    def test_deux_millimetres_changent_le_hash(self):
        entree = _entree_ecole()
        bougee = remplacer(entree, surfaces=(
            remplacer(entree.surfaces[0], longueur_m=51.102),))
        self.assertNotEqual(bougee.hash_entree, entree.hash_entree)

    def test_le_hash_ne_voit_jamais_un_float_brut(self):
        """Le bruit d'accumulation flottante ne change pas le hash."""
        entree = _entree_ecole()
        bruitee = remplacer(entree, surfaces=(
            remplacer(entree.surfaces[0],
                      longueur_m=51.10 + 1e-13, largeur_m=25.62 - 1e-13),))
        self.assertEqual(bruitee.hash_entree, entree.hash_entree)

    def test_le_hash_est_ascii_donc_identique_windows_linux(self):
        """Aucun caractère non ASCII n'entre dans l'empreinte."""
        empreinte = _entree_aile_l().hash_entree
        self.assertEqual(len(empreinte), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in empreinte))

    def test_changer_un_kit_change_le_hash(self):
        entree = _entree_ecole()
        autre = remplacer(entree, kits=(KIT_AO_PAYSAGE,),
                          parametres=_parametres((KIT_AO_PAYSAGE,)))
        self.assertNotEqual(autre.hash_entree, entree.hash_entree)

    def test_l_ordre_des_cles_n_influe_pas(self):
        entree = _entree_ecole()
        document = json.loads(json.dumps(entree.vers_dict()))
        self.assertEqual(hash_entree(document), entree.hash_entree)


class SchemaVersionne(unittest.TestCase):
    def test_le_document_porte_sa_version(self):
        self.assertEqual(_entree_ecole().vers_dict()["schema_version"],
                         SCHEMA_VERSION)

    def test_un_document_sans_version_est_refuse(self):
        with self.assertRaises(SchemaIncompatible):
            migrer({"repere": "X"})

    def test_un_document_plus_recent_que_le_moteur_est_refuse(self):
        with self.assertRaises(SchemaIncompatible):
            migrer({"schema_version": SCHEMA_VERSION + 5})

    def test_une_migration_manquante_est_refusee_explicitement(self):
        with self.assertRaises(SchemaIncompatible):
            migrer({"schema_version": SCHEMA_VERSION - 1},
                   vers=SCHEMA_VERSION)

    def test_type_de_surface_inconnu(self):
        with self.assertRaises(SchemaIncompatible):
            surface_depuis_dict({"type": "trapeze", "repere": "X"})

    def test_le_fichier_de_schema_est_publie_et_valide(self):
        chemin = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "calepinage", "schema.json")
        with open(chemin, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
        self.assertEqual(schema["title"], "EntreeCalepinage")
        for cle in ("surfaces", "kits", "parametres"):
            self.assertIn(cle, schema["properties"])
        for cle in ("surface", "kit", "obstacle", "zone", "parametres",
                    "rives", "coupure"):
            self.assertIn(cle, schema["$defs"])


class ResultatPorteLeCouple(unittest.TestCase):
    def test_le_resultat_porte_hash_et_version(self):
        entree = _entree_ecole()
        resultat = optimiser(entree.surfaces[0], entree.parametres,
                             entree.obstacles)
        sortie = ResultatCalepinage.depuis_resultat(entree, resultat,
                                                    plancher=300,
                                                    verdict="engagement tenu")
        self.assertEqual(sortie.hash_entree, entree.hash_entree)
        self.assertEqual(sortie.version_moteur, VERSION_MOTEUR)
        self.assertEqual(sortie.modules, 314)
        self.assertAlmostEqual(sortie.kwc, 314 * 0.625, delta=1e-9)
        self.assertTrue(sortie.optimal)

    def test_aller_retour_du_resultat(self):
        entree = _entree_ecole()
        resultat = optimiser(entree.surfaces[0], entree.parametres,
                             entree.obstacles)
        sortie = ResultatCalepinage.depuis_resultat(entree, resultat)
        refaite = ResultatCalepinage.depuis_dict(sortie.vers_dict())
        self.assertEqual(refaite.vers_dict(), sortie.vers_dict())
        self.assertEqual(refaite.methode, "dp_exact_1cm")


class RivesEtParametresSerialises(unittest.TestCase):
    def test_les_quatre_rives_survivent(self):
        rives = Rives(laterale_m=0.35, extremite_m=0.35, acrotere_m=0.28,
                      joint_m=0.45)
        surface = SurfaceRectangle(repere="R", longueur_m=10.0, largeur_m=8.0,
                                   rives=rives)
        refaite = surface_depuis_dict(surface_vers_dict(surface))
        self.assertAlmostEqual(refaite.rives.acrotere_m, 0.28)
        self.assertAlmostEqual(refaite.rives.joint_m, 0.45)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
