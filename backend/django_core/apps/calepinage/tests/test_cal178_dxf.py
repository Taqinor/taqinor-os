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
    document_dxf, octets_dxf,
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

    def test_la_toiture_porte_le_contour_et_les_pans(self):
        # Un contour + un pan.
        self.assertEqual(self.comptes.get(CALQUE_TOITURE), 2)

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
        self.document = document_dxf(self.geometrie)

    def test_les_modules_sont_des_points(self):
        self.assertIsNone(self.geometrie['module_m'])
        types = {e.dxftype() for e in self.document.modelspace()
                 if e.dxf.layer == CALQUE_MODULES}
        self.assertEqual(types, {'POINT'})

    def test_le_compte_reste_juste(self):
        modules = [e for e in self.document.modelspace()
                   if e.dxf.layer == CALQUE_MODULES]
        self.assertEqual(len(modules), 2)
