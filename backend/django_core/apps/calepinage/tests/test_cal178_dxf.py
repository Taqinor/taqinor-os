"""CAL178 — le DXF produit se RELIT, et son calque MODULES compte juste.

L'essai est un ALLER-RETOUR : on écrit le DXF, on le relit avec ``ezdxf`` et on
compte. C'est la seule vérification qui prouve qu'un bureau d'études pourra
l'ouvrir — un fichier « écrit sans erreur » peut très bien être illisible.

Essais PURS : ni base, ni WeasyPrint. ``ezdxf`` est déjà une dépendance du
dépôt (elle n'y servait qu'en lecture) : aucune n'est ajoutée.

Run :
    python manage.py test apps.calepinage.tests.test_cal178_dxf -v2
"""
import io

from django.test import SimpleTestCase

from apps.calepinage.services.export_dxf import (
    CALQUE_COTES, CALQUE_MODULES, CALQUE_OBSTACLES, CALQUE_TOITURE, CALQUES,
    _document_dxf, octets_dxf,
)
from apps.calepinage.services.planche import geometrie_de_planche

from .test_cal171_planche import LAYOUT


def relire(octets):
    """Relit le DXF exactement comme le ferait le logiciel du client."""
    import ezdxf

    return ezdxf.read(io.StringIO(octets.decode('utf-8')))


def par_calque(document):
    compte = {}
    for entite in document.modelspace():
        compte.setdefault(entite.dxf.layer, 0)
        compte[entite.dxf.layer] += 1
    return compte


class AllerRetourDxfTest(SimpleTestCase):
    def setUp(self):
        self.geometrie = geometrie_de_planche(LAYOUT)
        self.document = relire(octets_dxf(self.geometrie))
        self.comptes = par_calque(self.document)

    def test_le_fichier_se_relit(self):
        self.assertIsNotNone(self.document.modelspace())

    def test_les_quatre_calques_sont_declares(self):
        for nom, _couleur in CALQUES:
            self.assertIn(nom, self.document.layers,
                          'calque « %s » absent' % nom)

    def test_le_calque_modules_porte_exactement_les_modules_du_layout(self):
        poses = sum(len(pan['modules']) for pan in self.geometrie['pans'])
        self.assertEqual(poses, 2)
        self.assertEqual(self.comptes.get(CALQUE_MODULES), poses)

    def test_la_toiture_ne_double_pas_un_pan_egal_au_contour(self):
        # ACAL604 — dans LAYOUT, le pan EST le contour : une seule polyligne.
        self.assertEqual(self.comptes.get(CALQUE_TOITURE), 1)

    def test_un_pan_distinct_du_contour_est_conserve(self):
        geometrie = dict(self.geometrie)
        pan = dict(geometrie['pans'][0])
        pan['points'] = [(x + 1.0, y) for x, y in pan['points']]
        geometrie['pans'] = [pan]
        comptes = par_calque(relire(octets_dxf(geometrie)))
        self.assertEqual(comptes.get(CALQUE_TOITURE), 2)

    def test_les_obstacles_sont_sur_leur_calque(self):
        self.assertEqual(self.comptes.get(CALQUE_OBSTACLES), 1)

    def test_les_cotes_sont_sur_leur_calque_et_en_metres(self):
        # Deux lignes de cote + leurs deux textes.
        self.assertEqual(self.comptes.get(CALQUE_COTES), 4)
        textes = [e.dxf.text for e in self.document.modelspace()
                  if e.dxftype() == 'TEXT']
        self.assertTrue(textes)
        for texte in textes:
            self.assertTrue(texte.endswith(' m'), texte)

    def test_l_unite_du_dessin_est_le_metre(self):
        from ezdxf import units

        self.assertEqual(self.document.header['$INSUNITS'], units.M)

    def test_la_geometrie_est_a_l_echelle_du_terrain(self):
        # Le contour relu mesure une dizaine de mètres, pas un degré.
        contour = [e for e in self.document.modelspace()
                   if e.dxf.layer == CALQUE_TOITURE][0]
        points = [(p[0], p[1]) for p in contour.get_points()]
        largeur = max(p[0] for p in points) - min(p[0] for p in points)
        self.assertGreater(largeur, 5.0)
        self.assertLess(largeur, 30.0)


class ModuleSansEmpriseTest(SimpleTestCase):
    """Sans emprise SOURCÉE, un module reste un POINT — jamais un rectangle."""

    def setUp(self):
        layout = dict(LAYOUT)
        layout.pop('panelWatt', None)
        self.geometrie = geometrie_de_planche(layout)
        self.document = _document_dxf(self.geometrie)

    def test_les_modules_sont_des_points(self):
        self.assertIsNone(self.geometrie['module_m'])
        types = {e.dxftype() for e in self.document.modelspace()
                 if e.dxf.layer == CALQUE_MODULES}
        self.assertEqual(types, {'POINT'})

    def test_le_compte_reste_juste(self):
        modules = [e for e in self.document.modelspace()
                   if e.dxf.layer == CALQUE_MODULES]
        self.assertEqual(len(modules), 2)


class CotesDuToitSeulDxfTest(SimpleTestCase):
    """ACAL603 — le DXF cote le toit seul, jamais la boîte avec obstacles."""

    def test_un_obstacle_hors_rive_ne_change_pas_les_cotes(self):
        from apps.calepinage.services.planche import texte_de_longueur

        from .test_cal171_planche import _layout_avec_obstacles_hors_rive

        geometrie = geometrie_de_planche(_layout_avec_obstacles_hors_rive())
        document = relire(octets_dxf(geometrie))
        textes = sorted(e.dxf.text for e in document.modelspace()
                        if e.dxftype() == 'TEXT')
        x0, y0, x1, y1 = geometrie['etendue_toit']
        self.assertEqual(textes, sorted([texte_de_longueur(x1 - x0),
                                         texte_de_longueur(y1 - y0)]))
        e0, f0, e1, f1 = geometrie['etendue']
        self.assertNotIn(texte_de_longueur(e1 - e0), textes)


class EmpriseVraieDxfTest(SimpleTestCase):
    """ACAL604 — chaque module du DXF a l'emprise vraie, sans recouvrement."""

    def test_48_modules_portrait_donnent_48_polylignes_de_1_303_m(self):
        from .test_cal171_planche import (
            _layout_de_48_modules, _se_recouvrent,
        )

        geometrie = geometrie_de_planche(_layout_de_48_modules('portrait'))
        modules = [e for e in relire(octets_dxf(geometrie)).modelspace()
                   if e.dxf.layer == CALQUE_MODULES]
        self.assertEqual(len(modules), 48)
        carres = [[(p[0], p[1]) for p in e.get_points()] for e in modules]
        for carre in carres:
            largeur = max(p[0] for p in carre) - min(p[0] for p in carre)
            self.assertAlmostEqual(largeur, 1.303, places=3)
        for i, a in enumerate(carres):
            for b in carres[i + 1:]:
                self.assertFalse(_se_recouvrent(a, b))
