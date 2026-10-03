"""AGR309 — schéma forage → pompe → variateur → panneaux → bassin →
irrigation, et courbe constructeur avec son point de fonctionnement, en SVG
serveur. Tests PURS (aucune base, aucun rendu WeasyPrint)."""
import xml.etree.ElementTree as ET

from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole import schema as S
from apps.ventes.quote_engine.agricole.synthese import synthese_agricole

SVG_NS = '{http://www.w3.org/2000/svg}'

#: Courbe constructeur OSP 30/8 (contrat stock ``produit_pompage.json``) ; le
#: point (30 m³/h, 60 m) est celui de la fixture agricole de
#: ``test_figures_parite.py`` (``AGRICOLE_ETUDE`` : hmt 60, débit 30).
COURBE_OSP_30_8 = [[0, 91], [12, 85], [24, 70], [30, 60], [36, 43], [39, 34]]


def _synthese(schema=None, point_fonctionnement=None):
    s = {'schema': {'profondeur_m': 90, 'niveau_m': 40, 'distance_m': 25,
                    'hmt_m': 60, 'bassin': None}}
    if schema is not None:
        s['schema'] = schema
    if point_fonctionnement is not None:
        s['point_fonctionnement'] = point_fonctionnement
    return s


def _textes(svg):
    racine = ET.fromstring(svg)
    return [''.join(t.itertext()) for t in racine.iter(f'{SVG_NS}text')]


class Agr309SchemaTests(SimpleTestCase):

    def test_le_svg_se_parse_en_xml_valide(self):
        racine = ET.fromstring(S.schema_svg(_synthese()))
        self.assertEqual(racine.tag, f'{SVG_NS}svg')
        self.assertTrue(racine.get('width').endswith('mm'))

    def test_valeurs_saisies_ecrites(self):
        textes = ' | '.join(_textes(S.schema_svg(_synthese())))
        self.assertIn('Profondeur 90 m', textes)
        self.assertIn('Niveau 40 m', textes)
        self.assertIn('HMT 60 m', textes)
        self.assertIn('Distance 25 m', textes)

    def test_sans_profondeur_aucun_libelle_de_profondeur(self):
        svg = S.schema_svg(_synthese(schema={
            'profondeur_m': None, 'niveau_m': 40, 'distance_m': None,
            'hmt_m': 60, 'bassin': None}))
        self.assertNotIn('Profondeur', svg)
        self.assertNotIn('data-valeur="profondeur_m"', svg)
        self.assertNotIn('Distance', svg)
        # Jamais un tiret chiffré à la place.
        self.assertNotIn('— m', svg)
        self.assertNotIn('None', svg)

    def test_bassin_dessine_seulement_s_il_est_declare(self):
        sans = S.schema_svg(_synthese())
        self.assertNotIn('data-etape="bassin"', sans)
        avec = S.schema_svg(_synthese(schema={
            'profondeur_m': 90, 'niveau_m': 40, 'distance_m': 25,
            'hmt_m': 60, 'bassin': 60}))
        self.assertIn('data-etape="bassin"', avec)
        self.assertIn('60 m³', ' '.join(_textes(avec)))

    def test_ordre_des_etapes(self):
        svg = S.schema_svg(_synthese())
        positions = [svg.index(f'data-etape="{e}"') for e in
                     ('forage', 'pompe', 'variateur', 'panneaux',
                      'irrigation')]
        self.assertEqual(positions, sorted(positions))

    def test_etiquettes_traduites_en_arabe_et_anglais(self):
        ar = ' '.join(_textes(S.schema_svg(_synthese(), langue='ar')))
        self.assertIn(S.LIBELLES['pompe']['ar'], ar)
        self.assertNotIn('Pompe', ar)
        en = ' '.join(_textes(S.schema_svg(_synthese(), langue='en')))
        self.assertIn('Borehole', en)
        self.assertIn('Depth 90 m', en)

    def test_une_designation_avec_script_ressort_echappee(self):
        svg = S.schema_svg(_synthese(),
                           libelle_pompe='<script>alert(1)</script>')
        self.assertNotIn('<script>', svg)
        self.assertIn('&lt;script&gt;', svg)
        ET.fromstring(svg)  # toujours du XML valide
        courbe = S.courbe_svg(
            _synthese(point_fonctionnement={
                'courbe': COURBE_OSP_30_8,
                'point': {'debit_m3h': 30, 'hmt_m': 60}}),
            libelle_pompe='<script>x</script>')
        self.assertNotIn('<script>', courbe)
        ET.fromstring(courbe)


class Agr309CourbeTests(SimpleTestCase):

    def test_sans_courbe_courbe_svg_vaut_none(self):
        self.assertIsNone(S.courbe_svg(_synthese()))
        self.assertIsNone(S.courbe_svg(_synthese(
            point_fonctionnement={'courbe': [[0, 91]], 'point': None})))
        self.assertIsNone(S.courbe_svg({}))
        self.assertIn('courbe constructeur non disponible',
                      S.TEXTE_COURBE_ABSENTE['fr'].lower())

    def test_le_point_est_dessine_aux_coordonnees_hmt_debit(self):
        svg = S.courbe_svg(_synthese(point_fonctionnement={
            'courbe': COURBE_OSP_30_8,
            'point': {'debit_m3h': 30, 'hmt_m': 60}}))
        racine = ET.fromstring(svg)
        cercles = [c for c in racine.iter(f'{SVG_NS}circle')
                   if c.get('data-point') == 'fonctionnement']
        self.assertEqual(len(cercles), 1)
        q_borne, h_borne = 39 * 1.05, 91 * 1.1
        x, y = S.coordonnees(30, 60, q_borne, h_borne)
        self.assertAlmostEqual(float(cercles[0].get('cx')), x, places=1)
        self.assertAlmostEqual(float(cercles[0].get('cy')), y, places=1)
        self.assertEqual(float(cercles[0].get('data-debit-m3h')), 30)
        self.assertEqual(float(cercles[0].get('data-hmt-m')), 60)
        # La courbe passe par ce même point (30, 60) : même coordonnée.
        poly = next(racine.iter(f'{SVG_NS}polyline')).get('points')
        self.assertIn('%.1f,%.1f' % (x, y), poly)

    def test_courbe_svg_se_parse_en_xml_valide(self):
        svg = S.courbe_svg(_synthese(point_fonctionnement={
            'courbe': COURBE_OSP_30_8,
            'point': {'debit_m3h': 30.5, 'hmt_m': 58.7}}), langue='ar')
        ET.fromstring(svg)
        self.assertIn('58,7', svg)


class Agr309SyntheseTests(SimpleTestCase):

    def test_la_synthese_porte_le_schema_svg(self):
        data = {'etude': {'hmt_m': 60, 'distance_champ_m': 25,
                          'source': {'profondeur_forage_m': 90}},
                'all_items': []}
        s = synthese_agricole(data)
        self.assertIn('schema_svg', s)
        ET.fromstring(s['schema_svg'])
        self.assertEqual(s['schema_svg'], S.schema_svg(s))
        self.assertIn('Profondeur 90 m', s['schema_svg'])
        self.assertNotIn('Niveau', s['schema_svg'])
