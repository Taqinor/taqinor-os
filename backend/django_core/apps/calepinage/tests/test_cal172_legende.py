"""CAL172 — nord, échelle, légende et orientations sur la planche.

Essais PURS (ni base, ni WeasyPrint). La garantie qui compte est la dernière :
un pan dont l'azimut n'est pas connu n'affiche PAS « 0° ». Le zéro d'une mesure
absente est un mensonge lisible — et c'est exactement celui qu'un plan imprimé
propage jusqu'au chantier.

Run :
    python manage.py test apps.calepinage.tests.test_cal172_legende -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.planche import (
    LARGEUR_BARRE_MM, entrees_de_legende, geometrie_de_planche,
    lignes_d_orientation, longueur_de_barre, svg_de_planche,
    texte_d_orientation,
)
from apps.calepinage.tests.test_cal171_planche import LAYOUT


class LegendeTest(SimpleTestCase):
    def test_ne_liste_que_ce_qui_est_dessine(self):
        libelles = [e[2] for e in
                    entrees_de_legende(geometrie_de_planche(LAYOUT))]
        self.assertIn('Contour relevé', libelles)
        self.assertIn('Pan de toiture', libelles)
        self.assertIn('Module posé', libelles)
        self.assertIn('Obstacle relevé', libelles)
        # Aucune zone interdite dans ce document : aucune entrée non plus.
        self.assertNotIn('Zone interdite ou réservée', libelles)
        self.assertNotIn('Obstacle à confirmer', libelles)

    def test_un_obstacle_non_releve_ajoute_son_entree(self):
        layout = dict(LAYOUT)
        zone = dict(LAYOUT['zones'][0])
        zone['obstacles'] = [dict(LAYOUT['zones'][0]['obstacles'][0],
                                  provenance='PLAN')]
        layout['zones'] = [zone]
        libelles = [e[2] for e in
                    entrees_de_legende(geometrie_de_planche(layout))]
        self.assertIn('Obstacle à confirmer', libelles)


class OrientationTest(SimpleTestCase):
    def test_les_deux_mesures_connues_sont_ecrites(self):
        pan = geometrie_de_planche(LAYOUT)['pans'][0]
        self.assertEqual(texte_d_orientation(pan),
                         'Pan Sud — azimut 180° · inclinaison 15°')

    def test_un_pan_sans_azimut_n_affiche_jamais_zero_degre(self):
        layout = {'outline': LAYOUT['outline'],
                  'zones': [{'id': 'z1', 'label': 'Pan sans relevé',
                             'vertices': LAYOUT['zones'][0]['vertices']}]}
        geometrie = geometrie_de_planche(layout)
        self.assertEqual(texte_d_orientation(geometrie['pans'][0]), '')
        self.assertEqual(lignes_d_orientation(geometrie), ())
        svg = svg_de_planche(geometrie, titre='Sans relevé')
        self.assertNotIn('azimut', svg)
        self.assertNotIn('0°', svg)

    def test_une_seule_mesure_connue_n_invente_pas_l_autre(self):
        layout = {'outline': LAYOUT['outline'],
                  'zones': [{'id': 'z1', 'label': 'Pan',
                             'pitchDeg': 12.5,
                             'vertices': LAYOUT['zones'][0]['vertices']}]}
        pan = geometrie_de_planche(layout)['pans'][0]
        self.assertEqual(texte_d_orientation(pan), 'Pan — inclinaison 12,5°')


class BarreEchelleTest(SimpleTestCase):
    def test_la_barre_porte_une_longueur_ronde_qui_tient(self):
        metres, millimetres = longueur_de_barre(4.0)
        self.assertIn(metres, (1.0, 2.0, 5.0, 10.0))
        self.assertLessEqual(millimetres, LARGEUR_BARRE_MM)

    def test_un_terrain_immense_garde_une_barre_bornee(self):
        metres, millimetres = longueur_de_barre(0.05)
        self.assertLessEqual(millimetres, LARGEUR_BARRE_MM)
        self.assertGreater(metres, 0.0)


class PlancheCompleteTest(SimpleTestCase):
    def setUp(self):
        self.svg = svg_de_planche(geometrie_de_planche(LAYOUT),
                                  titre='Toiture atelier')

    def test_le_nord_et_l_echelle_sont_sur_la_planche(self):
        self.assertIn('>N</text>', self.svg)
        self.assertIn('LÉGENDE', self.svg)
        self.assertIn('ORIENTATION DES PANS', self.svg)

    def test_la_barre_graphique_reste_la_reference(self):
        # CAL194 a ajouté une échelle NOMMÉE (le pack réglementaire l'exige),
        # mais elle ne REMPLACE pas la barre : « 1/200 » devient faux dès la
        # première photocopie A3 -> A4. La barre est donc toujours là, et la
        # fraction porte sa condition de validité.
        self.assertIn('<rect x="14" y="', self.svg)  # la barre d'échelle
        # L'apostrophe est échappée dans le SVG (`&#x27;`) : on cherche donc
        # le texte tel qu'il est RÉELLEMENT écrit dans le document.
        self.assertIn('barre d&#x27;échelle', self.svg)
        self.assertIn('non réduit', self.svg)
