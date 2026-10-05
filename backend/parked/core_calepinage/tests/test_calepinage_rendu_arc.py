# -*- coding: utf-8 -*-
"""AOF69 — l'arc : cotes radiales et tangentielles, murets, SAT sur le RENDU.

Géométrie témoin : la résidence en aile courbe de la planche 06I remise le
27/07/2026 — rayon extérieur 274,00 m, bande 10,90 m, développé extérieur
68,05 m, trois segments séparés par des murets de 0,45 m au ras.

La preuve centrale exigée par la tâche : **le SAT est rejoué sur la géométrie
RENDUE et pas seulement calculée**. Le test le montre par un cas où les deux
divergent — deux tables jointives en coordonnées curvilignes, donc « disjointes »
au calcul d'intervalles, se recouvrent réellement au bord intérieur une fois
posées en rectangles rigides sur la courbe.
"""

import math
import unittest

from core.calepinage.rendu import arc as A
from core.calepinage.rendu import couleurs as C
from core.calepinage.rendu.feuille import Feuille

RAYON_EXT = 274.0
LARGEUR = 10.90
DEVELOPPE = 68.05
MURET = 0.45
SEGMENT_1 = 20.55
SEGMENT_2 = 23.00
SEGMENT_3 = 23.60
DEPART_2 = SEGMENT_1 + MURET                       # 21,00
DEPART_3 = DEPART_2 + SEGMENT_2 + MURET            # 44,45

TABLE_L = 1.134
TABLE_W = 4.70


def geometrie():
    return A.GeometrieArc(rayon_exterieur=RAYON_EXT, largeur=LARGEUR,
                          developpe=DEVELOPPE)


def segments():
    return (A.SegmentArc("S1", 0.0, SEGMENT_1),
            A.SegmentArc("S2", DEPART_2, DEPART_2 + SEGMENT_2),
            A.SegmentArc("S3", DEPART_3, DEPART_3 + SEGMENT_3))


def murets():
    return (A.Muret(SEGMENT_1 + MURET / 2, MURET, "joint S1/S2"),
            A.Muret(DEPART_2 + SEGMENT_2 + MURET / 2, MURET, "joint S2/S3"))


def rangee(depart, nombre, jeu, segment, bas=3.0):
    """Une rangée de tables espacées de ``jeu`` le long du développé."""
    posees = []
    abscisse = depart
    for _ in range(nombre):
        posees.append(A.TableArc(abscisse, abscisse + TABLE_L, bas,
                                 bas + TABLE_W, segment=segment))
        abscisse += TABLE_L + jeu
    return tuple(posees)


class GeometrieDeLArc(unittest.TestCase):
    def test_le_developpe_extremite_a_extremite_est_respecte(self):
        geo = geometrie()
        self.assertAlmostEqual(geo.angle_total, DEVELOPPE / RAYON_EXT, places=12)
        self.assertAlmostEqual(geo.rayon_interieur, RAYON_EXT - LARGEUR,
                               places=12)

    def test_l_arc_est_centre_et_symetrique(self):
        geo = geometrie()
        gauche = geo.point(0.0, 0.0)
        droite = geo.point(DEVELOPPE, 0.0)
        self.assertAlmostEqual(gauche[0], -droite[0], places=9)
        self.assertAlmostEqual(gauche[1], droite[1], places=9)
        milieu = geo.point(DEVELOPPE / 2.0, 0.0)
        self.assertAlmostEqual(milieu[0], 0.0, places=9)

    def test_la_longueur_du_bord_exterieur_vaut_le_developpe(self):
        geo = geometrie()
        points = geo.points_d_arc(0.0, DEVELOPPE, LARGEUR, cordes=4000)
        longueur = sum(math.dist(points[i], points[i + 1])
                       for i in range(len(points) - 1))
        self.assertAlmostEqual(longueur, DEVELOPPE, places=4)

    def test_le_bord_interieur_est_plus_court_que_l_exterieur(self):
        geo = geometrie()

        def longueur(y):
            points = geo.points_d_arc(0.0, DEVELOPPE, y, cordes=2000)
            return sum(math.dist(points[i], points[i + 1])
                       for i in range(len(points) - 1))

        self.assertLess(longueur(0.0), longueur(LARGEUR))

    def test_une_geometrie_impossible_est_refusee(self):
        for parametres in (dict(rayon_exterieur=0.0, largeur=1.0, developpe=1.0),
                           dict(rayon_exterieur=10.0, largeur=0.0, developpe=1.0),
                           dict(rayon_exterieur=10.0, largeur=1.0, developpe=0.0),
                           dict(rayon_exterieur=10.0, largeur=12.0, developpe=1.0)):
            with self.subTest(**parametres):
                with self.assertRaises(ValueError):
                    A.GeometrieArc(**parametres)


class TablesRigidesAuRepereTangent(unittest.TestCase):
    def test_une_table_reste_un_rectangle_rigide(self):
        geo = geometrie()
        polygone = geo.polygone_rigide(10.0, 10.0 + TABLE_L, 3.0, 3.0 + TABLE_W)
        self.assertEqual(len(polygone), 4)
        cotes = [math.dist(polygone[i], polygone[(i + 1) % 4]) for i in range(4)]
        self.assertAlmostEqual(cotes[0], TABLE_L, places=9)
        self.assertAlmostEqual(cotes[1], TABLE_W, places=9)
        self.assertAlmostEqual(cotes[2], TABLE_L, places=9)
        self.assertAlmostEqual(cotes[3], TABLE_W, places=9)

    def test_deux_tables_voisines_ne_sont_pas_paralleles(self):
        geo = geometrie()
        a = geo.polygone_rigide(10.0, 10.0 + TABLE_L, 3.0, 3.0 + TABLE_W)
        b = geo.polygone_rigide(30.0, 30.0 + TABLE_L, 3.0, 3.0 + TABLE_W)

        def angle(polygone):
            x0, y0 = polygone[0]
            x1, y1 = polygone[1]
            return math.atan2(y1 - y0, x1 - x0)

        self.assertNotAlmostEqual(angle(a), angle(b), places=4)


class TestDesAxesSeparateurs(unittest.TestCase):
    CARRE = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))

    def test_deux_carres_disjoints(self):
        autre = tuple((x + 2.5, y) for x, y in self.CARRE)
        self.assertAlmostEqual(A.separation(self.CARRE, autre), 1.5, places=9)
        self.assertFalse(A.se_recouvrent(self.CARRE, autre))

    def test_deux_carres_qui_se_recouvrent(self):
        autre = tuple((x + 0.4, y) for x, y in self.CARRE)
        self.assertLess(A.separation(self.CARRE, autre), 0.0)
        self.assertTrue(A.se_recouvrent(self.CARRE, autre))

    def test_deux_carres_jointifs_ne_se_recouvrent_pas(self):
        autre = tuple((x + 1.0, y) for x, y in self.CARRE)
        self.assertAlmostEqual(A.separation(self.CARRE, autre), 0.0, places=9)
        self.assertFalse(A.se_recouvrent(self.CARRE, autre))

    def test_le_controle_cite_la_paire_fautive(self):
        autre = tuple((x + 0.4, y) for x, y in self.CARRE)
        with self.assertRaises(A.TablesEnRecouvrement) as capture:
            A.verifier_non_recouvrement((self.CARRE, autre))
        self.assertIn("0", str(capture.exception))
        self.assertIn("1", str(capture.exception))


class LeSATEstRejoueSurLeRENDU(unittest.TestCase):
    """La preuve centrale : calcul disjoint, rendu recouvrant."""

    def _feuille(self):
        return Feuille("IMPLANTATION — AILE COURBE", "relevé du 27/07/2026",
                       (-40, 40), (-2, 14))

    def test_des_tables_jointives_au_calcul_se_recouvrent_une_fois_posees(self):
        geo = geometrie()
        jointives = rangee(5.0, 4, 0.0, "S1")
        # au calcul d'intervalles, ces tables sont disjointes : [a, b] puis
        # [b, c]. Une fois RENDUES en rectangles rigides sur la courbe, leurs
        # coins intérieurs se croisent.
        for premiere, seconde in zip(jointives, jointives[1:]):
            self.assertAlmostEqual(seconde.debut, premiere.fin, places=12)
        with self._feuille() as feuille:
            A.dessiner_tables(feuille, geo, jointives, C.VERT_TABLE_CONTOUR,
                              C.VERT_TABLE_FOND)
            with self.assertRaises(A.TablesEnRecouvrement) as capture:
                A.verifier_tables_dessinees(feuille)
        self.assertIn("recouvrement", str(capture.exception))

    def test_un_jeu_suffisant_rend_le_calepinage_posable(self):
        geo = geometrie()
        with self._feuille() as feuille:
            A.dessiner_tables(feuille, geo, rangee(5.0, 6, 0.20, "S1"),
                              C.VERT_TABLE_CONTOUR, C.VERT_TABLE_FOND)
            self.assertTrue(A.verifier_tables_dessinees(feuille))

    def test_le_controle_relit_bien_les_polygones_DESSINES(self):
        geo = geometrie()
        tables = rangee(5.0, 3, 0.20, "S1")
        with self._feuille() as feuille:
            attendus = A.dessiner_tables(feuille, geo, tables,
                                         C.VERT_TABLE_CONTOUR,
                                         C.VERT_TABLE_FOND)
            A.dessiner_murets(feuille, geo, murets(), C.NOIR_GEOMETRIE,
                              C.FOND_BLOC)
            relus = A.tables_dessinees(feuille)
        self.assertEqual(len(relus), len(tables))   # les murets sont exclus
        for attendu, relu in zip(attendus, relus):
            for point_attendu, point_relu in zip(attendu, relu):
                self.assertAlmostEqual(point_attendu[0], point_relu[0], places=9)
                self.assertAlmostEqual(point_attendu[1], point_relu[1], places=9)


class RecouvrementEviteEtMarges(unittest.TestCase):
    def test_le_min_et_le_max_de_separation_sont_imprimables(self):
        geo = geometrie()
        tables = (A.TableArc(5.0, 5.0 + TABLE_L, 3.0, 3.0 + TABLE_W, "S1"),
                  A.TableArc(6.5, 6.5 + TABLE_L, 3.0, 3.0 + TABLE_W, "S1"),
                  A.TableArc(9.0, 9.0 + TABLE_L, 3.0, 3.0 + TABLE_W, "S1"))
        polygones = tuple(geo.polygone_rigide(t.debut, t.fin, t.bas, t.haut)
                          for t in tables)
        minimum, maximum = A.recouvrement_evite(polygones)
        self.assertGreater(minimum, 0.0)
        self.assertLess(minimum, maximum)

    def test_moins_de_deux_tables_ne_produit_aucune_separation(self):
        self.assertEqual(A.recouvrement_evite(()), (None, None))
        self.assertEqual(A.recouvrement_evite((((0, 0), (1, 0), (1, 1)),)),
                         (None, None))

    def test_la_separation_rendue_est_plus_faible_que_le_jeu_curviligne(self):
        """Au bord intérieur, la courbe MANGE une part du jeu annoncé."""
        geo = geometrie()
        jeu = 0.20
        tables = rangee(5.0, 2, jeu, "S1")
        polygones = tuple(geo.polygone_rigide(t.debut, t.fin, t.bas, t.haut)
                          for t in tables)
        minimum, _maximum = A.recouvrement_evite(polygones)
        self.assertLess(minimum, jeu)
        self.assertGreater(minimum, 0.0)

    def test_les_marges_par_segment(self):
        tables = (rangee(1.0, 2, 0.20, "S1")
                  + rangee(DEPART_2 + 0.5, 3, 0.20, "S2"))
        marges = A.marges_par_segment(segments(), tables)
        noms = [nom for nom, _debut, _fin in marges]
        self.assertEqual(noms, ["S1", "S2", "S3"])
        self.assertAlmostEqual(marges[0][1], 1.0, places=9)
        self.assertAlmostEqual(marges[1][1], 0.5, places=9)
        # un segment vide se déclare vide sur toute sa longueur
        self.assertAlmostEqual(marges[2][1], SEGMENT_3, places=9)
        self.assertAlmostEqual(marges[2][2], SEGMENT_3, places=9)


class CotesRadialesEtTangentielles(unittest.TestCase):
    def _feuille(self):
        return Feuille("T", "s", (-40, 40), (-2, 14))

    def test_une_cote_radiale_mesure_la_vraie_distance(self):
        geo = geometrie()
        with self._feuille() as feuille:
            cote = A.rdim(feuille, geo, 7.60, 0.0, LARGEUR, C.BLEU_MESURE)
            libelle = feuille.axe.texts[-1].get_text()
        self.assertAlmostEqual(cote.longueur, LARGEUR, places=9)
        self.assertEqual(libelle, "10,90")

    def test_une_cote_tangentielle_exige_son_developpe(self):
        geo = geometrie()
        with self._feuille() as feuille:
            with self.assertRaises(ValueError) as capture:
                A.tdim(feuille, geo, 0.0, SEGMENT_1, 6.62, C.BLEU_MESURE)
            self.assertIn("développé", str(capture.exception))
            self.assertEqual(len(feuille.axe.texts), 0)

    def test_la_corde_tracee_est_plus_courte_que_le_developpe_cote(self):
        geo = geometrie()
        with self._feuille() as feuille:
            cote = A.tdim(feuille, geo, 0.0, SEGMENT_1, 6.62, C.BLEU_MESURE,
                          contenu="20,55")
            libelle = feuille.axe.texts[-1].get_text()
        self.assertLess(cote.longueur, SEGMENT_1)
        self.assertEqual(libelle, "20,55")

    def test_une_cote_orange_reste_orange(self):
        geo = geometrie()
        with self._feuille() as feuille:
            A.rdim(feuille, geo, 19.80, 0.0, 0.78,
                   C.couleur_du_statut(C.StatutCote.A_CONFIRMER),
                   contenu="0,78")
            couleur = feuille.axe.texts[-1].get_color()
        self.assertEqual(couleur, C.ORANGE_A_CONFIRMER)


class MuretsEtBandes(unittest.TestCase):
    def test_les_murets_sont_des_VOLUMES_pas_des_traits(self):
        geo = geometrie()
        with Feuille("T", "s", (-40, 40), (-2, 14)) as feuille:
            poses = A.dessiner_murets(feuille, geo, murets(),
                                      C.NOIR_GEOMETRIE, C.FOND_BLOC)
            marques = [p.get_gid() for p in feuille.axe.patches]
        self.assertEqual(len(poses), 2)
        self.assertEqual(marques, [A.GID_MURET, A.GID_MURET])
        for polygone in poses:
            cotes = [math.dist(polygone[i], polygone[(i + 1) % 4])
                     for i in range(4)]
            self.assertAlmostEqual(cotes[0], MURET, places=9)
            self.assertAlmostEqual(cotes[1], LARGEUR, places=9)

    def test_les_deux_bords_courbes_sont_traces(self):
        geo = geometrie()
        with Feuille("T", "s", (-40, 40), (-2, 14)) as feuille:
            A.dessiner_bandes(feuille, geo, C.NOIR_GEOMETRIE)
            traits = len(feuille.axe.lines)
        self.assertEqual(traits, 2)

    def test_la_planche_arc_entiere_sort_en_octets(self):
        geo = geometrie()
        with Feuille("IMPLANTATION — RÉSIDENCE AILE COURBE",
                     "relevé contradictoire du 27/07/2026", (-40, 40),
                     (-4, 16)) as feuille:
            A.dessiner_bandes(feuille, geo, C.NOIR_GEOMETRIE)
            A.dessiner_murets(feuille, geo, murets(), C.NOIR_GEOMETRIE,
                              C.FOND_BLOC)
            A.dessiner_tables(feuille, geo, rangee(1.0, 12, 0.20, "S1"),
                              C.VERT_TABLE_CONTOUR, C.VERT_TABLE_FOND)
            A.rdim(feuille, geo, 7.60, 0.0, LARGEUR, C.BLEU_MESURE,
                   contenu="10,87 (confirmé)")
            A.tdim(feuille, geo, 0.0, SEGMENT_1, 6.62, C.BLEU_MESURE,
                   contenu="20,55")
            A.verifier_tables_dessinees(feuille)
            octets = feuille.pdf()
        self.assertTrue(octets.startswith(b"%PDF"))


if __name__ == "__main__":            # pragma: no cover
    unittest.main()
