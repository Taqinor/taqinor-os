"""CAL171 — la planche se compose de la géométrie STOCKÉE, ou elle refuse.

Ces essais sont PURS : ils ne touchent ni la base ni WeasyPrint. C'est
délibéré — la composition du SVG est là où les erreurs se logent (repère
retourné, obstacle pivoté, emprise inventée), et elle doit rester vérifiable
partout, y compris sur un poste sans bibliothèque graphique. Le rendu PDF
lui-même n'ajoute rien à vérifier ici : il délègue à ``core.pdf.render_pdf``
(ARC11), déjà couvert par ses propres essais.

Run :
    python manage.py test apps.calepinage.tests.test_cal171_planche -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.planche import (
    PlancheRefusee, dimensions_module, echelle_de_dessin, geometrie_de_planche,
    html_de_planche, nom_de_fichier, svg_de_planche, texte_de_longueur,
)

#: Un document de conception minimal mais RÉEL : contour en ``[lat, lng]``,
#: pan en ``[lng, lat]``, un obstacle relevé et deux modules posés.
LAYOUT = {
    'version': 2,
    'outline': [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999],
                [33.5001, -7.6]],
    'panelWatt': 720,
    'zones': [{
        'id': 'z1',
        'label': 'Pan Sud',
        'vertices': [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001],
                     [-7.6, 33.5001]],
        'obstacles': [{'id': 'obs-1', 'centerLng': -7.59995,
                       'centerLat': 33.50005, 'lengthM': 0.8, 'widthM': 1.2,
                       'type': 'cheminee', 'provenance': 'RELEVE'}],
        'geometry': {
            'azimuthDeg': 180.0, 'tiltDeg': 15.0, 'count': 2,
            'origin': [-7.6, 33.5],
            'panels': [{'cx': 1.0, 'cy': 1.0}, {'cx': 3.5, 'cy': 1.0}],
        },
    }],
}


class GeometrieDePlancheTest(SimpleTestCase):
    def test_refuse_un_calepinage_sans_conception(self):
        for vide in (None, {}, {'zones': []}, {'outline': []}):
            with self.assertRaises(PlancheRefusee) as capture:
                geometrie_de_planche(vide)
            self.assertEqual(capture.exception.champ, 'roof_layout')
            self.assertIn('conception', str(capture.exception).lower())

    def test_projette_le_contour_et_les_pans_en_metres(self):
        geometrie = geometrie_de_planche(LAYOUT)
        self.assertEqual(len(geometrie['contour']), 4)
        self.assertEqual(len(geometrie['pans']), 1)
        x0, y0, x1, y1 = geometrie['etendue']
        # 0,0001° de latitude ≈ 11,1 m ; l'étendue doit être de cet ordre et
        # JAMAIS de l'ordre du degré (repère non projeté).
        self.assertGreater(x1 - x0, 5.0)
        self.assertLess(x1 - x0, 30.0)
        self.assertGreater(y1 - y0, 5.0)
        self.assertLess(y1 - y0, 30.0)

    def test_les_modules_sont_les_centres_reellement_poses(self):
        pan = geometrie_de_planche(LAYOUT)['pans'][0]
        self.assertEqual(len(pan['modules']), 2)
        # L'écart entre les deux centres est celui du document (3,5 - 1,0).
        self.assertAlmostEqual(pan['modules'][1][0] - pan['modules'][0][0],
                               2.5, places=6)
        self.assertAlmostEqual(pan['modules'][1][1], pan['modules'][0][1],
                               places=6)

    def test_l_obstacle_garde_son_orientation_nord_sud(self):
        obstacle = geometrie_de_planche(LAYOUT)['obstacles'][0]
        # ``lengthM`` est l'étendue NORD-SUD, ``widthM`` l'EST-OUEST : les
        # confondre pivoterait l'obstacle de 90°.
        self.assertAlmostEqual(obstacle['hauteur'], 0.8, places=6)
        self.assertAlmostEqual(obstacle['largeur'], 1.2, places=6)

    def test_un_pan_sans_azimut_ne_se_voit_pas_attribuer_zero(self):
        layout = {'outline': LAYOUT['outline'],
                  'zones': [{'id': 'z1',
                             'vertices': LAYOUT['zones'][0]['vertices']}]}
        pan = geometrie_de_planche(layout)['pans'][0]
        self.assertIsNone(pan['azimut_deg'])
        self.assertIsNone(pan['pente_deg'])


class DimensionsModuleTest(SimpleTestCase):
    def test_dimensions_sourcees_par_le_kit_declare(self):
        self.assertEqual(dimensions_module({'panelWatt': 720}),
                         (2.384, 1.303))

    def test_puissance_inconnue_ne_produit_aucune_dimension(self):
        # Une emprise plausible mais non sourcée se lirait comme une emprise
        # mesurée : on préfère l'absence.
        self.assertIsNone(dimensions_module({'panelWatt': 615}))
        self.assertIsNone(dimensions_module({}))


class SvgDePlancheTest(SimpleTestCase):
    def setUp(self):
        self.svg = svg_de_planche(geometrie_de_planche(LAYOUT),
                                  titre='Toiture atelier')

    def test_le_svg_est_un_a3_paysage_autonome(self):
        self.assertTrue(self.svg.lstrip().startswith('<?xml'))
        self.assertIn('width="420mm" height="297mm"', self.svg)
        self.assertIn('viewBox="0 0 420 297"', self.svg)
        self.assertTrue(self.svg.rstrip().endswith('</svg>'))

    def test_aucun_acces_reseau_dans_le_document(self):
        # La seule URL admise est l'espace de noms SVG, qui n'est jamais
        # RÉSOLU par un rendu : c'est un identifiant, pas une ressource.
        corps = self.svg.replace('http://www.w3.org/2000/svg', '')
        for interdit in ('http://', 'https://', '<image', '@import', 'url('):
            self.assertNotIn(interdit, corps)

    def test_le_dessin_reste_dans_les_marges_de_la_feuille(self):
        import re

        coordonnees = [float(v) for v in
                       re.findall(r'(?:x1|x2|y1|y2)="([-\d.]+)"', self.svg)]
        coordonnees += [float(c) for couple in
                        re.findall(r'points="([^"]+)"', self.svg)
                        for point in couple.split()
                        for c in point.split(',')]
        self.assertTrue(coordonnees)
        self.assertGreaterEqual(min(coordonnees), 0.0)
        self.assertLessEqual(max(coordonnees), 420.0)

    def test_les_cotes_sont_en_metres_a_la_francaise(self):
        self.assertIn(' m<', self.svg)
        self.assertEqual(texte_de_longueur(12.345), '12,35 m')

    def test_les_deux_modules_sont_dessines(self):
        # Emprise sourcée (720 Wc) -> deux polygones de module.
        self.assertGreaterEqual(self.svg.count('stroke="#2e7d32"'), 2)

    def test_le_titre_est_echappe(self):
        svg = svg_de_planche(geometrie_de_planche(LAYOUT),
                             titre='Toiture <script>')
        self.assertNotIn('<script>', svg)
        self.assertIn('&lt;script&gt;', svg)

    def test_l_echelle_tient_dans_la_zone_de_dessin(self):
        etendue = geometrie_de_planche(LAYOUT)['etendue']
        echelle = echelle_de_dessin(etendue)
        largeur_mm = (etendue[2] - etendue[0]) * echelle
        self.assertLessEqual(round(largeur_mm, 3),
                             420.0 - 2 * 12.0 - 84.0 + 0.001)
        self.assertGreater(echelle, 0.0)


class EnveloppeHtmlTest(SimpleTestCase):
    def test_le_html_porte_le_svg_et_le_format_a3(self):
        html = html_de_planche('<svg/>')
        self.assertIn('size:A3 landscape', html)
        self.assertIn('<svg/>', html)

    def test_le_nom_de_fichier_est_assaini(self):
        class Faux:
            pk = 41
            titre = 'Toiture / atelier «Bouskoura»'

        nom = nom_de_fichier(Faux(), 'pdf')
        self.assertTrue(nom.startswith('calepinage-41-'))
        self.assertTrue(nom.endswith('.pdf'))
        self.assertNotIn('/', nom)
        self.assertNotIn(' ', nom)
