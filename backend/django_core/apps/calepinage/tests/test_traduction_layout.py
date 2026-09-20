"""CAL78 — le traducteur ``roof_layout`` v2 → entrée du moteur, sous garde.

CE QUI EST PROUVÉ ICI
---------------------
* un document D'OR (contour, pans, obstacles, zones d'exclusion, épingle) rend
  une entrée RÉELLEMENT acceptée par ``core/calepinage/schema.json`` — la
  validation est dérivée du fichier de schéma lui-même (clés admises, clés
  requises, énumérés), sans ``jsonschema`` qui n'est pas au ``requirements``
  du dépôt (même discipline que ``core/tests/test_calepinage_schema.py``) ;
* un document SANS kit chiffrable est REFUSÉ en nommant le champ manquant —
  jamais un repli silencieux sur les cotes du module d'un autre écran ;
* le RÉGIME DE PREUVE remonte tel quel : un obstacle venu du PLAN rend le
  document non engageable, avec le motif du moteur, mot pour mot ;
* la LATITUDE du site est déclarée dans la politique de pas (décision CAL78,
  documentée en tête de ``services/traduction.py``) et elle CHANGE réellement
  l'espacement — sans quoi la déclarer ne servirait à rien ;
* pans, obstacles et zones passent par la MÊME projection : une zone tracée
  sur un obstacle se retrouve au même endroit que lui.

Aucune base de données : ``SimpleTestCase``.

Run :
    python manage.py test apps.calepinage.tests.test_traduction_layout -v2
"""
import io
import json
import math
import os

from django.test import SimpleTestCase

from apps.calepinage.services.degagements import RETRAIT_ATELIER_M
from apps.calepinage.services.traduction import (
    TraductionRefusee, entree_depuis_layout,
)

CHEMIN_SCHEMA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    'core', 'calepinage', 'schema.json')


def _schema():
    with io.open(CHEMIN_SCHEMA, encoding='utf-8') as fh:
        return json.load(fh)


def _document_or():
    """Le document D'OR : deux pans, un obstacle typé, une zone interdite.

    Les cotes du panneau sont PORTÉES par le document (aucun produit rattaché
    dans un test sans base) : c'est le second chemin autorisé du traducteur.
    Les coordonnées sont à Casablanca — un lieu réel, pas un (0, 0) qui
    projetterait au large du golfe de Guinée.
    """
    return {
        'version': 2,
        'pin': {'lat': 33.5, 'lng': -7.6},
        'panelWatt': 720,
        'panelLengthM': 2.278,
        'panelWidthM': 1.134,
        'activeAreaId': 'z1',
        'zones': [
            {
                'id': 'z1',
                'label': 'Pan principal',
                'roofType': 'flat',
                'vertices': _rectangle(-7.6, 33.5, 14.0, 10.0),
                'obstacles': [
                    {
                        'id': 'obs-1',
                        'centerLng': -7.6,
                        'centerLat': 33.5,
                        'lengthM': 0.8,
                        'widthM': 1.2,
                        'type': 'cheminee',
                        'heightM': 1.2,
                        'provenance': 'MESURE',
                    },
                ],
            },
            {
                'id': 'z2',
                'label': 'Pan annexe',
                'roofType': 'flat',
                'vertices': _rectangle(-7.59985, 33.5, 6.0, 6.0),
            },
        ],
        'exclusionZones': [
            {
                'id': 'zx-1',
                'nature': 'INTERDITE',
                'vertices': _rectangle(-7.59997, 33.49998, 2.0, 1.5),
                'setbackM': 0.3,
            },
        ],
    }


def _rectangle(lon0, lat0, largeur_m, hauteur_m):
    """Un rectangle en ``[[lng, lat], …]`` autour de ``(lon0, lat0)``.

    La conversion mètres → degrés est celle de ``services/zones.py``
    (``projeteur_local``) : le test et le code mesurent la même Terre.
    """
    dlon = largeur_m / (111320.0 * math.cos(math.radians(lat0))) / 2.0
    dlat = hauteur_m / 110540.0 / 2.0
    return [[lon0 - dlon, lat0 - dlat], [lon0 + dlon, lat0 - dlat],
            [lon0 + dlon, lat0 + dlat], [lon0 - dlon, lat0 + dlat]]


class LeDocumentDOrEstAccepteParLeSchema(SimpleTestCase):
    """Le contrat du moteur, vérifié sur la sortie RÉELLE du traducteur."""

    def setUp(self):
        self.schema = _schema()
        self.document = entree_depuis_layout(_document_or()).document

    def test_aucune_cle_hors_du_schema(self):
        # ``additionalProperties: false`` à la racine : une clé de plus est
        # un document REFUSÉ par le moteur, pas une extension tolérée.
        admises = set(self.schema['properties'])
        self.assertFalse(set(self.document) - admises)

    def test_toutes_les_cles_requises_sont_la(self):
        for cle in self.schema['required']:
            self.assertIn(cle, self.document)

    def test_les_enumeres_du_schema_sont_respectes(self):
        defs = self.schema['$defs']
        for surface in self.document['surfaces']:
            self.assertIn(surface['type'], defs['surface']
                          ['properties']['type']['enum'])
            self.assertIn(surface['axe_rangee'], defs['surface']
                          ['properties']['axe_rangee']['enum'])
            self.assertGreaterEqual(len(surface['contour']), 3)
        for kit in self.document['kits']:
            self.assertIn(kit['orientation'],
                          defs['kit']['properties']['orientation']['enum'])
            for cle in defs['kit']['required']:
                self.assertIn(cle, kit)
        for obstacle in self.document['obstacles']:
            self.assertIn(obstacle['provenance'],
                          defs['obstacle']['properties']['provenance']['enum'])
        for zone in self.document['zones']:
            self.assertIn(zone['nature'],
                          defs['zone']['properties']['nature']['enum'])
        self.assertIn(self.document['parametres']['mode_pose'],
                      defs['parametres']['properties']['mode_pose']['enum'])

    def test_le_document_se_relit_par_le_noyau(self):
        """La preuve ultime : le noyau lui-même le désérialise."""
        from core.calepinage.serialisation import EntreeCalepinage

        entree = EntreeCalepinage.depuis_dict(self.document)
        self.assertEqual(len(entree.surfaces), 2)
        self.assertEqual(len(entree.obstacles), 1)
        self.assertEqual(len(entree.zones), 1)
        self.assertEqual(len(entree.hash_entree), 64)

    def test_les_deux_pans_gardent_leur_identifiant(self):
        self.assertEqual([s['repere'] for s in self.document['surfaces']],
                         ['z1', 'z2'])

    def test_le_retrait_de_rive_est_celui_de_l_atelier_par_defaut(self):
        rives = self.document['parametres']['rives']
        self.assertEqual(rives['laterale_m'], RETRAIT_ATELIER_M)
        self.assertEqual(rives['extremite_m'], RETRAIT_ATELIER_M)


class LeKitVientDuDocumentOuDuProduitJamaisDAilleurs(SimpleTestCase):

    def test_les_cotes_du_document_font_le_kit(self):
        kit = entree_depuis_layout(_document_or()).document['kits'][0]
        self.assertEqual(kit['module_long_m'], 2.278)
        self.assertEqual(kit['module_court_m'], 1.134)
        self.assertEqual(kit['puissance_module_wc'], 720.0)

    def test_sans_cotes_le_document_est_refuse_en_nommant_le_champ(self):
        document = _document_or()
        document.pop('panelLengthM')
        document.pop('panelWidthM')
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout(document)
        self.assertEqual(refus.exception.champ, 'panelLengthM')
        self.assertIn('COTES', str(refus.exception))

    def test_sans_puissance_le_document_est_refuse_en_nommant_le_champ(self):
        document = _document_or()
        document.pop('panelWatt')
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout(document)
        self.assertEqual(refus.exception.champ, 'panelWatt')

    def test_aucun_repli_sur_le_kit_villa(self):
        """Le refus ne doit JAMAIS rendre un kit par défaut (720 Wc villa)."""
        from core.calepinage.types import KIT_VILLA_720

        document = _document_or()
        document.pop('panelLengthM')
        document.pop('panelWidthM')
        try:
            traduction = entree_depuis_layout(document)
        except TraductionRefusee:
            return
        self.assertNotEqual(traduction.kit.module_long_m,
                            KIT_VILLA_720.module_long_m)

    def test_les_cotes_transmises_priment_sur_celles_du_document(self):
        traduction = entree_depuis_layout(_document_or(),
                                          cotes_module=(2.384, 1.303))
        self.assertEqual(traduction.kit.module_long_m, 2.384)


class LeRegimeDePreuveRemonteTelQuel(SimpleTestCase):

    def test_un_obstacle_releve_laisse_le_compte_engageable(self):
        traduction = entree_depuis_layout(_document_or())
        self.assertTrue(traduction.engageable)
        self.assertEqual(traduction.motifs_non_engageable, ())

    def test_un_obstacle_du_plan_rend_le_compte_non_engageable(self):
        document = _document_or()
        document['zones'][0]['obstacles'][0]['provenance'] = 'PLAN'
        traduction = entree_depuis_layout(document)
        self.assertFalse(traduction.engageable)
        self.assertEqual(len(traduction.motifs_non_engageable), 1)
        self.assertIn('obs-1', traduction.motifs_non_engageable[0])

    def test_le_vocabulaire_ao_est_accepte(self):
        """``MESURE`` ≡ ``RELEVE`` : refuser l'une ferait rougir un producteur."""
        document = _document_or()
        document['zones'][0]['obstacles'][0]['provenance'] = 'MESURE_DOUTEUX'
        obstacle = entree_depuis_layout(document).document['obstacles'][0]
        self.assertEqual(obstacle['provenance'], 'RELEVE_DOUTEUX')

    def test_une_provenance_inconnue_est_refusee_en_nommant_le_champ(self):
        document = _document_or()
        document['zones'][0]['obstacles'][0]['provenance'] = 'AU_PIF'
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout(document)
        self.assertIn('provenance', refus.exception.champ)

    def test_le_degagement_respecte_le_plancher_de_provenance(self):
        """Une provenance qui EXIGE plus que l'atelier gagne (jamais l'inverse)."""
        from core.calepinage.obstacles import degagement_par_provenance
        from core.calepinage.types import Provenance

        document = _document_or()
        obstacle_brut = document['zones'][0]['obstacles'][0]
        obstacle_brut['type'] = 'antenne'          # atelier : 0,30 m
        obstacle_brut['provenance'] = 'DEVINE'     # plancher : 0,50 m
        obstacle = entree_depuis_layout(document).document['obstacles'][0]
        self.assertEqual(obstacle['degagement_m'],
                         degagement_par_provenance(Provenance.DEVINE))

    def test_le_degagement_de_l_atelier_est_annonce_non_source(self):
        obstacle = entree_depuis_layout(
            _document_or()).document['obstacles'][0]
        self.assertEqual(obstacle['degagement_m'], 0.50)   # cheminée
        self.assertIn('non sourcée', obstacle['regle_appliquee'])


class LaLatitudeDuSiteEstDeclaree(SimpleTestCase):
    """DÉCISION CAL78 : le traducteur DÉCLARE la latitude à ``AntiOmbrage``.

    Elle est disponible (l'épingle du document), le MAJEUR correspondant est
    déjà journalisé (``core/calepinage/version.py`` 2.0.0, PV65/CAL167), et
    AUCUN golden ne bouge : l'adaptateur villa reste sans latitude.
    """

    def test_la_politique_porte_la_latitude_de_l_epingle(self):
        traduction = entree_depuis_layout(_document_or())
        self.assertEqual(traduction.latitude_deg, 33.5)
        self.assertEqual(traduction.politique.latitude_deg, 33.5)

    def test_la_latitude_change_reellement_l_espacement(self):
        """Déclarer la latitude sans effet mesurable serait un faux confort."""
        from core.calepinage.politique_pas import AntiOmbrage

        traduction = entree_depuis_layout(_document_or())
        kit = traduction.kit
        self.assertNotAlmostEqual(
            traduction.politique.pas_apres_rangee(kit, 0.0),
            AntiOmbrage().pas_apres_rangee(kit, 0.0), places=3)

    def test_la_version_du_moteur_porte_deja_ce_majeur(self):
        from core.calepinage.version import VERSION_MOTEUR, version_tuple

        self.assertGreaterEqual(version_tuple(VERSION_MOTEUR)[0], 2)

    def test_un_toit_en_pente_se_pose_affleurant(self):
        from core.calepinage.politique_pas import Affleurant

        document = _document_or()
        for pan in document['zones']:
            pan['roofType'] = 'pitched'
            pan['pitchDeg'] = 15.0
        traduction = entree_depuis_layout(document)
        self.assertIsInstance(traduction.politique, Affleurant)

    def test_chaque_pan_a_sa_politique(self):
        document = _document_or()
        document['zones'][1]['roofType'] = 'pitched'
        document['zones'][1]['pitchDeg'] = 20.0
        politiques = dict(entree_depuis_layout(document).politiques)
        self.assertEqual(politiques['z1'].code, 'ANTI_OMBRAGE')
        self.assertEqual(politiques['z2'].code, 'AFFLEURANT')


class UneSeuleProjectionPourToutLeDocument(SimpleTestCase):

    def test_la_zone_tombe_bien_sur_le_pan(self):
        """Zone et pan viennent du même repère : la zone est DANS le pan."""
        traduction = entree_depuis_layout(_document_or())
        pan = traduction.document['surfaces'][0]['contour']
        zone = traduction.document['zones'][0]['sommets']
        xmin = min(p[0] for p in pan)
        xmax = max(p[0] for p in pan)
        ymin = min(p[1] for p in pan)
        ymax = max(p[1] for p in pan)
        for x, y in zone:
            self.assertGreaterEqual(x, xmin)
            self.assertLessEqual(x, xmax)
            self.assertGreaterEqual(y, ymin)
            self.assertLessEqual(y, ymax)

    def test_le_pan_mesure_ce_qu_il_a_ete_trace(self):
        """14 m × 10 m tracés ⇒ 14 m × 10 m projetés (tolérance mm)."""
        contour = entree_depuis_layout(
            _document_or()).document['surfaces'][0]['contour']
        largeur = max(p[0] for p in contour) - min(p[0] for p in contour)
        hauteur = max(p[1] for p in contour) - min(p[1] for p in contour)
        # L'axe est-ouest (module unique plein sud) : x = est, y = nord.
        self.assertAlmostEqual(largeur, 14.0, places=2)
        self.assertAlmostEqual(hauteur, 10.0, places=2)

    def test_l_obstacle_garde_ses_dimensions(self):
        obstacle = entree_depuis_layout(
            _document_or()).document['obstacles'][0]
        self.assertAlmostEqual(obstacle['x1'] - obstacle['x0'], 1.2, places=3)
        self.assertAlmostEqual(obstacle['y1'] - obstacle['y0'], 0.8, places=3)


class LesRefusNommentToujoursLeChamp(SimpleTestCase):

    def test_un_document_sans_pan_est_refuse(self):
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout({'panelWatt': 720})
        self.assertEqual(refus.exception.champ, 'zones')

    def test_un_document_qui_n_est_pas_un_objet_est_refuse(self):
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout([])
        self.assertEqual(refus.exception.champ, 'roof_layout')

    def test_un_contour_a_deux_sommets_est_refuse(self):
        document = _document_or()
        document['zones'][0]['vertices'] = [[-7.6, 33.5], [-7.6, 33.6]]
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout(document)
        self.assertEqual(refus.exception.champ, 'zones[0].vertices')

    def test_un_obstacle_sans_centre_est_refuse(self):
        document = _document_or()
        document['zones'][0]['obstacles'][0].pop('centerLng')
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout(document)
        self.assertEqual(refus.exception.champ,
                         'zones[0].obstacles[0].centerLng')

    def test_une_zone_d_exclusion_illisible_garde_le_refus_de_cal68(self):
        document = _document_or()
        document['exclusionZones'][0]['nature'] = 'INVENTEE'
        with self.assertRaises(TraductionRefusee) as refus:
            entree_depuis_layout(document)
        self.assertEqual(refus.exception.champ, 'exclusionZones[0]')
        self.assertIn('Nature de zone inconnue', str(refus.exception))
