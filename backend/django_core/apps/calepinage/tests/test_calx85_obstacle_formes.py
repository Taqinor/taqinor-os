"""CALX85 — le contrat des obstacles NON rectangulaires du document v2.

CE QUE CE FICHIER GARDE
-----------------------
`$defs/obstacle` ne décrivait qu'un rectangle centré, et le code n'a aucune
autre forme (`apps/web/src/scripts/roofPro11/types.ts`, `obstaclesUi.ts` ne
dessine qu'un anneau rectangulaire) : une cheminée ronde et un édicule
biscornu passaient l'un comme l'autre pour des rectangles. CALX85 ouvre le
polygone et le cercle. Trois promesses sont affirmées ici :

1. **Les trois clés sont ADDITIVES.** Un obstacle SANS `forme` se relit comme
   le RECTANGLE d'aujourd'hui, byte pour byte ; l'`exemple` du schéma n'a pas
   bougé.
2. **Une forme porte sa géométrie, ou elle est REFUSÉE.** Un `polygone` sans
   `contour` d'au moins trois sommets, un `cercle` sans `rayonM` : refusés en
   nommant le champ, par la porte d'import RÉELLE
   (``services/io_layout.py::valider_document``). Aucun rayon n'est arrondi
   depuis le rectangle, aucun contour n'est fabriqué (D-CALX 7).
3. **Le dégagement par type n'est pas touché.** `CLEARANCE_BY_TYPE` (PV61)
   s'applique autour de la forme RÉELLE ; le schéma n'en porte aucune valeur.

`EXEMPLE_OBSTACLES` ci-dessous est le tableau que les lanes 3D (`apps/web`)
liront TEL QUEL : les TROIS formes, plus l'obstacle historique sans `forme`.
Ses coordonnées sont des valeurs d'EXEMPLE, dans le repère de l'exemple du
schéma.

Run :
    python manage.py test apps.calepinage.tests.test_calx85_obstacle_formes
"""
from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.io_layout import (
    ImportLayoutRefuse, valider_document,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
SCHEMA = json.loads((ECHANTILLONS / 'roof_layout_v2.schema.json')
                    .read_text(encoding='utf-8'))

#: Les QUATRE états que le document sait porter depuis CALX85 : l'obstacle
#: historique (aucune `forme` — lu comme un rectangle), le rectangle
#: explicite, le polygone et le cercle.
EXEMPLE_OBSTACLES = [
    {
        'id': 'obs-1',
        'centerLng': 3.0,
        'centerLat': 2.0,
        'lengthM': 0.8,
        'widthM': 0.8,
        'type': 'cheminee',
        'heightM': 1.2,
        'provenance': 'RELEVE',
    },
    {
        'id': 'obs-2',
        'forme': 'rectangle',
        'centerLng': 5.0,
        'centerLat': 2.0,
        'lengthM': 1.2,
        'widthM': 0.6,
        'type': 'ventilation',
        'provenance': 'RELEVE',
    },
    {
        'id': 'obs-3',
        'forme': 'polygone',
        'contour': [[6.0, 3.0], [7.2, 3.0], [7.2, 4.1], [6.6, 4.6],
                    [6.0, 4.1]],
        'centerLng': 6.6,
        'centerLat': 3.8,
        'type': 'edicule',
        'provenance': 'RELEVE',
    },
    {
        'id': 'obs-4',
        'forme': 'cercle',
        'centerLng': 8.0,
        'centerLat': 1.5,
        'rayonM': 0.35,
        'type': 'cheminee',
        'provenance': 'RELEVE',
    },
]


def document_avec_formes():
    """L'exemple du schéma, augmenté du fragment de CALX85."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['zones'][0]['obstacles'] = copy.deepcopy(EXEMPLE_OBSTACLES)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`forme`, `contour` et `rayonM` sont OPTIONNELLES."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_aucune_forme(self):
        """La preuve que le document historique n'a pas été réécrit."""
        for zone in SCHEMA['exemple'].get('zones', []):
            for obstacle in zone.get('obstacles', []):
                self.assertNotIn('forme', obstacle)
                self.assertNotIn('contour', obstacle)
                self.assertNotIn('rayonM', obstacle)

    def test_un_obstacle_sans_forme_reste_lu_comme_un_rectangle(self):
        """Le cas d'aujourd'hui : aucune clé de forme, aucun refus."""
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        valider_document(copy.deepcopy(SCHEMA['exemple']))
        historique = EXEMPLE_OBSTACLES[0]
        self.assertNotIn('forme', historique)
        for cle in ('centerLng', 'centerLat', 'lengthM', 'widthM'):
            self.assertIn(cle, historique)

    def test_un_document_avec_les_trois_formes_est_valide(self):
        self.assertEqual(erreurs(document_avec_formes()), [])

    def test_retirer_les_cles_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_formes()
        document['zones'][0]['obstacles'] = copy.deepcopy(
            SCHEMA['exemple']['zones'][0]['obstacles'])
        self.assertEqual(document, SCHEMA['exemple'])


class LesTroisFormesTest(SimpleTestCase):
    """L'énumération est FERMÉE, et l'exemple les exerce toutes."""

    def setUp(self):
        self.obstacle = SCHEMA['$defs']['obstacle']

    def test_l_enumeration_est_fermee(self):
        self.assertEqual(self.obstacle['properties']['forme']['enum'],
                         ['rectangle', 'polygone', 'cercle'])

    def test_l_exemple_exerce_les_trois_formes(self):
        formes = {obstacle['forme'] for obstacle in EXEMPLE_OBSTACLES
                  if 'forme' in obstacle}
        self.assertEqual(formes, {'rectangle', 'polygone', 'cercle'})

    def test_l_exemple_garde_l_obstacle_historique(self):
        sans_forme = [obstacle for obstacle in EXEMPLE_OBSTACLES
                      if 'forme' not in obstacle]
        self.assertTrue(
            sans_forme,
            "Sans un obstacle SANS `forme`, l'exemple ne prouverait pas que "
            'le rectangle implicite survit.')

    def test_aucun_degagement_ni_dimension_par_defaut(self):
        for nom in ('forme', 'contour', 'rayonM'):
            sous_schema = self.obstacle['properties'][nom]
            for interdit in ('default', 'examples'):
                self.assertNotIn(
                    interdit, sous_schema,
                    f'`{nom}` porte « {interdit} » : le schéma livrerait une '
                    f'géométrie que personne n’a relevée.')
        self.assertNotIn('dégagement', json.dumps(self.obstacle).lower())

    def test_un_polygone_exige_trois_sommets_dans_sa_definition(self):
        self.assertEqual(self.obstacle['properties']['contour']['minItems'], 3)


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_formes())

    def test_un_polygone_sans_contour_nomme_la_cle_contour(self):
        document = document_avec_formes()
        del document['zones'][0]['obstacles'][2]['contour']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.obstacles.2')
        self.assertIn('contour', str(refus))

    def test_un_polygone_a_deux_sommets_nomme_la_cle_contour(self):
        document = document_avec_formes()
        document['zones'][0]['obstacles'][2]['contour'] = [[6.0, 3.0],
                                                           [7.2, 3.0]]
        refus = self._refus(document)
        self.assertIn('contour', refus.champ)

    def test_un_cercle_sans_rayon_nomme_la_cle_rayon(self):
        document = document_avec_formes()
        del document['zones'][0]['obstacles'][3]['rayonM']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.obstacles.3')
        self.assertIn('rayonM', str(refus),
                      "Aucun rayon n'est arrondi depuis le rectangle : le "
                      'message doit nommer la clé manquante.')

    def test_un_rayon_a_zero_nomme_le_champ(self):
        document = document_avec_formes()
        document['zones'][0]['obstacles'][3]['rayonM'] = 0
        refus = self._refus(document)
        self.assertIn('rayonM', refus.champ)

    def test_une_forme_inconnue_nomme_le_champ_forme(self):
        document = document_avec_formes()
        document['zones'][0]['obstacles'][1]['forme'] = 'ellipse'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.obstacles.1.forme')
        self.assertIn('ellipse', str(refus))

    def test_un_rectangle_explicite_n_exige_ni_contour_ni_rayon(self):
        document = document_avec_formes()
        rectangle = document['zones'][0]['obstacles'][1]
        self.assertNotIn('contour', rectangle)
        self.assertNotIn('rayonM', rectangle)
        valider_document(document)

    def test_un_sommet_a_trois_nombres_est_refuse(self):
        document = document_avec_formes()
        document['zones'][0]['obstacles'][2]['contour'][0] = [6.0, 3.0, 1.0]
        refus = self._refus(document)
        self.assertIn('contour', refus.champ)
