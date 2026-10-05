"""ACAL212 — l'analyse d'un plan DXF/PDF choisit le BON contour.

Le contour par défaut est l'entité FERMÉE de plus grande AIRE (jamais celle
qui a le plus de sommets), des segments LINE chaînés bout à bout forment un
contour, les arcs à ``bulge`` sont discrétisés, les entités sont listées et
choisissables par leur rang, et un DXF cp1252 est lu avec le bon encodage.
Vrais DXF fabriqués par ``ezdxf`` — aucun mock. Sans base de données.

Run ::

    python manage.py test apps.calepinage.tests.test_acal_analyse_plan -v 2
"""
from __future__ import annotations

import io
import math
import os
import tempfile

from django.test import SimpleTestCase

from apps.calepinage.services import import_plan


def _nouveau(version='R2010'):
    import ezdxf

    doc = ezdxf.new(version)
    doc.header['$INSUNITS'] = 6
    return doc


def _octets(doc):
    flux = io.StringIO()
    doc.write(flux)
    return flux.getvalue().encode('utf-8')


def _contour(octets, calque, **kw):
    analyse = import_plan.analyser_plan(octets)
    return import_plan.contour_du_calque(analyse, calque, **kw)


def _rectangle(largeur, hauteur, x0=0.0, y0=0.0):
    return [(x0, y0), (x0 + largeur, y0), (x0 + largeur, y0 + hauteur),
            (x0, y0 + hauteur)]


class LinesChaineesTest(SimpleTestCase):

    def _quatre_line(self, ecart=0.0):
        doc = _nouveau()
        doc.layers.add('MUR')
        pts = _rectangle(12, 8)
        for i in range(4):
            a, b = pts[i], pts[(i + 1) % 4]
            doc.modelspace().add_line(
                a, (b[0] + ecart * (i == 3), b[1]),
                dxfattribs={'layer': 'MUR'})
        return _octets(doc)

    def test_quatre_line_donnent_un_contour_ferme_12_x_8(self):
        contour = _contour(self._quatre_line(), 'MUR')
        self.assertEqual(len(contour), 4)
        cotes = import_plan.cotes_hors_tout(contour)
        self.assertEqual((cotes['largeur'], cotes['hauteur']), (12.0, 8.0))

    def test_quatre_segments_isoles_refus_nomme(self):
        doc = _nouveau()
        doc.layers.add('MUR')
        for i in range(4):          # quatre segments qui ne se touchent pas
            doc.modelspace().add_line((i * 10, 0), (i * 10 + 5, 0),
                                      dxfattribs={'layer': 'MUR'})
        with self.assertRaises(import_plan.PlanIllisible) as refus:
            _contour(_octets(doc), 'MUR')
        self.assertIn('tracé non fermé : 4 segments isolés',
                      str(refus.exception))
        self.assertEqual(refus.exception.champ, 'calque')


class ChoixDeL_entiteTest(SimpleTestCase):

    def _toit_et_ornement(self):
        """Le toit 10 x 6 (4 sommets) et un ornement 3 x 3 à 12 sommets."""
        doc = _nouveau()
        doc.layers.add('PLAN')
        escalier = [(20, 0), (21, 0), (21, 1), (22, 1), (22, 2), (23, 2),
                    (23, 3), (20, 3), (20, 2), (20.5, 2), (20.5, 1),
                    (20, 1)]
        doc.modelspace().add_lwpolyline(
            _rectangle(10, 6), close=True, dxfattribs={'layer': 'PLAN'})
        doc.modelspace().add_lwpolyline(
            escalier, close=True, dxfattribs={'layer': 'PLAN'})
        return _octets(doc)

    def test_plus_grande_aire_pas_plus_de_sommets(self):
        contour = _contour(self._toit_et_ornement(), 'PLAN')
        self.assertEqual(len(contour), 4)           # le toit, pas l'ornement
        cotes = import_plan.cotes_hors_tout(contour)
        self.assertEqual((cotes['largeur'], cotes['hauteur']), (10.0, 6.0))

    def test_la_parcelle_gagne_quand_elle_est_la_plus_grande(self):
        doc = _nouveau()
        doc.layers.add('0x')
        doc.modelspace().add_lwpolyline(
            _rectangle(10, 6), close=True, dxfattribs={'layer': '0x'})
        parcelle = [(0, 20), (10, 20), (20, 20), (30, 20), (40, 20),
                    (40, 30), (40, 40), (40, 50), (0, 50), (0, 40),
                    (0, 30), (0, 25)]
        doc.modelspace().add_lwpolyline(
            parcelle, close=True, dxfattribs={'layer': '0x'})
        analyse = import_plan.analyser_plan(_octets(doc))
        detail = analyse['calques'][0]['entites_detail']
        self.assertEqual([e['sommets'] for e in detail], [4, 12])
        contour = import_plan.contour_du_calque(analyse, '0x')
        self.assertEqual(len(contour), 12)           # la parcelle (1200 m2)
        roof = import_plan.contour_du_calque(analyse, '0x', entite=1)
        self.assertEqual(len(roof), 4)

    def test_entite_choisie_par_rang(self):
        octets = self._toit_et_ornement()
        analyse = import_plan.analyser_plan(octets)
        detail = analyse['calques'][0]['entites_detail']
        self.assertEqual([e['rang'] for e in detail], [1, 2])
        self.assertTrue(all(e['fermee'] for e in detail))
        self.assertEqual(detail[0]['aire'], 60.0)
        self.assertEqual(detail[0]['emprise'],
                         {'largeur': 10.0, 'hauteur': 6.0})
        ornement = import_plan.contour_du_calque(analyse, 'PLAN', entite=2)
        self.assertEqual(len(ornement), 12)

    def test_entite_inexistante_refusee_en_nommant_le_champ(self):
        analyse = import_plan.analyser_plan(self._toit_et_ornement())
        with self.assertRaises(import_plan.PlanIllisible) as refus:
            import_plan.contour_du_calque(analyse, 'PLAN', entite=9)
        self.assertEqual(refus.exception.champ, 'entite')


class BulgeTest(SimpleTestCase):

    def test_bulge_discretise(self):
        doc = _nouveau()
        doc.layers.add('ARC')
        # Rectangle 10 x 6 dont le côté droit est un DEMI-CERCLE (bulge 1).
        doc.modelspace().add_lwpolyline(
            [(0, 0, 0), (10, 0, 1), (10, 6, 0), (0, 6, 0)], format='xyb',
            close=True, dxfattribs={'layer': 'ARC'})
        contour = _contour(_octets(doc), 'ARC')
        self.assertGreater(len(contour), 8)         # arc non aplati en corde
        self.assertAlmostEqual(max(p[0] for p in contour), 13.0, places=6)
        for x, y in contour:
            if x > 10.0 + 1e-9:                     # points de l'arc
                self.assertAlmostEqual(
                    math.hypot(x - 10.0, y - 3.0), 3.0, places=6)


class Cp1252Test(SimpleTestCase):

    def test_dxf_cp1252_deux_calques_distincts_aux_noms_exacts(self):
        doc = _nouveau('R2000')
        for nom in ('Bâtiment', 'Bétiment'):
            doc.layers.add(nom)
            doc.modelspace().add_lwpolyline(
                _rectangle(5, 4), close=True, dxfattribs={'layer': nom})
        with tempfile.TemporaryDirectory() as dossier:
            chemin = os.path.join(dossier, 'plan.dxf')
            doc.saveas(chemin)
            with open(chemin, 'rb') as fichier:
                octets = fichier.read()
        with self.assertRaises(UnicodeDecodeError):  # vrai cp1252, pas UTF-8
            octets.decode('utf-8')
        analyse = import_plan.analyser_plan(octets)
        noms = sorted(calque['nom'] for calque in analyse['calques'])
        self.assertEqual(noms, ['Bâtiment', 'Bétiment'])


class MoinsDeTroisSommetsTest(SimpleTestCase):

    def test_contour_sous_trois_sommets_refuse(self):
        doc = _nouveau()
        doc.layers.add('FIL')
        doc.modelspace().add_lwpolyline(
            [(0, 0), (5, 0)], close=True, dxfattribs={'layer': 'FIL'})
        with self.assertRaises(import_plan.PlanIllisible) as refus:
            _contour(_octets(doc), 'FIL')
        self.assertIn('3 sommets', str(refus.exception))
