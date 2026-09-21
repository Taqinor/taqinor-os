"""CALX84 — le contrat `buildings[]` du document v2.

CE QUE CE FICHIER GARDE
-----------------------
`zones[].buildingId` (CAL59) désigne depuis longtemps un bâtiment que RIEN ne
décrit ; la hauteur saisie dans CAL60 vit dans une `Map` locale
(`apps/web/src/scripts/roofPro11/shadingUi.ts`), n'est jamais émise par
`serializeLayout` — rouvrir le document la perd — et la 3D extrude toujours
`FLOORS × FLOOR_HEIGHT_M`. CALX84 fait voyager la hauteur DANS le document.
Trois promesses sont affirmées ici :

1. **La clé est ADDITIVE.** Un document v2 sans `buildings` reste valide,
   l'`exemple` du schéma n'a pas bougé, et le même document avec la clé reste
   valide lui aussi. Un `buildingId` qui ne désigne aucun bâtiment décrit
   reste TOLÉRÉ : les documents d'aujourd'hui en portent déjà.
2. **Aucune hauteur n'est devinée** (D-CALX 7). `hauteurM: null` = mesure qui
   MANQUE, ce qui n'est pas 0 m ; l'hypothèse d'aujourd'hui reste une
   hypothèse que l'atelier affiche. Aucune hauteur n'est dérivée des étages.
3. **Une hauteur SAISIE arrive avec sa provenance.** Un `hauteurM` numérique
   sans `source` est REFUSÉ en nommant `source`, par la porte d'import RÉELLE
   (``services/io_layout.py::valider_document``).

`EXEMPLE_BATIMENTS` ci-dessous est le tableau que les lanes 3D (`apps/web`)
liront TEL QUEL : un bâtiment à hauteur SAISIE et tracée, un bâtiment dont
personne n'a mesuré la hauteur. Ses nombres sont des valeurs d'EXEMPLE.

Run :
    python manage.py test apps.calepinage.tests.test_calx84_batiments
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

#: DEUX bâtiments d'exemple. Le premier porte une hauteur SAISIE et dit d'où
#: elle vient ; le second n'en porte AUCUNE — c'est l'état qui laisse la 3D
#: sur son hypothèse affichée, et qui ne vaut surtout pas « 0 m ».
EXEMPLE_BATIMENTS = [
    {
        'id': 'bat-1',
        'label': 'Villa (exemple)',
        'hauteurM': 7.2,
        'etages': 2,
        'hauteurEtageM': 3.0,
        'source': 'mesurée au télémètre sur site',
    },
    {
        'id': 'bat-2',
        'label': 'Garage (exemple)',
        'hauteurM': None,
        'etages': None,
        'hauteurEtageM': None,
        'source': None,
    },
]


def document_avec_batiments():
    """L'exemple du schéma, augmenté du fragment de CALX84.

    L'exemple porte DÉJÀ `zones[0].buildingId = 'bat-1'` depuis CAL59 : le
    fragment ne fait que DÉCRIRE enfin ce bâtiment-là, sans toucher au pan.
    """
    document = copy.deepcopy(SCHEMA['exemple'])
    document['buildings'] = copy.deepcopy(EXEMPLE_BATIMENTS)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`buildings` est OPTIONNELLE : rien de ce qui existe ne bouge."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_pas_les_batiments(self):
        """La preuve que le document historique n'a pas été réécrit."""
        self.assertNotIn('buildings', SCHEMA['exemple'])

    def test_un_document_sans_batiment_reste_valide(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])

    def test_un_document_avec_batiments_est_valide(self):
        self.assertEqual(erreurs(document_avec_batiments()), [])

    def test_un_tableau_de_batiments_vide_est_valide(self):
        document = copy.deepcopy(SCHEMA['exemple'])
        document['buildings'] = []
        self.assertEqual(erreurs(document), [])

    def test_un_building_id_sans_batiment_decrit_reste_tolere(self):
        """Les documents d'aujourd'hui en portent déjà (CAL59)."""
        document = copy.deepcopy(SCHEMA['exemple'])
        document['zones'][0]['buildingId'] = 'bat-jamais-decrit'
        self.assertEqual(erreurs(document), [])
        valider_document(document)

    def test_retirer_la_cle_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_batiments()
        document.pop('buildings')
        self.assertEqual(document, SCHEMA['exemple'])

    def test_le_batiment_deja_designe_par_l_exemple_est_enfin_decrit(self):
        """CAL59 pose `buildingId`; CALX84 lui donne enfin un objet."""
        document = document_avec_batiments()
        designe = document['zones'][0]['buildingId']
        decrits = [batiment['id'] for batiment in document['buildings']]
        self.assertIn(designe, decrits)


class AucuneHauteurDevineeTest(SimpleTestCase):
    """L'absence de mesure est un FAIT, pas un trou à combler (D-CALX 7)."""

    def setUp(self):
        self.batiment = SCHEMA['$defs']['building']

    def test_une_hauteur_absente_vaut_null_jamais_zero(self):
        self.assertIn('null', self.batiment['properties']['hauteurM']['type'])
        self.assertEqual(
            self.batiment['properties']['hauteurM']['exclusiveMinimum'], 0,
            "Un `0` explicite se lirait « mesuré à ras » : une hauteur "
            "renseignée est strictement positive, une hauteur non renseignée "
            'vaut `null`.')

    def test_aucune_hauteur_par_defaut_dans_le_schema(self):
        for nom, sous_schema in self.batiment['properties'].items():
            for interdit in ('default', 'const', 'enum', 'examples'):
                self.assertNotIn(
                    interdit, sous_schema,
                    f'`{nom}` porte « {interdit} » : le schéma livrerait une '
                    f'hauteur que personne n’a mesurée.')

    def test_l_exemple_montre_les_deux_etats(self):
        hauteurs = [batiment['hauteurM'] for batiment in EXEMPLE_BATIMENTS]
        self.assertIn(None, hauteurs,
                      "L'exemple doit montrer un bâtiment NON MESURÉ : c'est "
                      "l'état qui laisse la 3D sur son hypothèse affichée.")
        self.assertTrue([valeur for valeur in hauteurs if valeur is not None])

    def test_un_batiment_non_mesure_n_a_pas_de_source(self):
        non_mesure = EXEMPLE_BATIMENTS[1]
        self.assertIsNone(non_mesure['hauteurM'])
        self.assertIsNone(non_mesure['source'])

    def test_seul_l_identifiant_est_obligatoire(self):
        self.assertEqual(self.batiment['required'], ['id'])


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_batiments())

    def test_une_hauteur_sans_source_nomme_la_cle_source(self):
        document = document_avec_batiments()
        del document['buildings'][0]['source']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'buildings.0')
        self.assertIn('source', str(refus),
                      'Le message doit NOMMER `source` : une hauteur sans '
                      "provenance n'est pas engageable.")

    def test_une_hauteur_avec_une_source_nulle_nomme_la_cle_source(self):
        document = document_avec_batiments()
        document['buildings'][0]['source'] = None
        refus = self._refus(document)
        self.assertIn('source', refus.champ)

    def test_une_hauteur_avec_une_source_vide_est_refusee(self):
        document = document_avec_batiments()
        document['buildings'][0]['source'] = ''
        refus = self._refus(document)
        self.assertIn('source', refus.champ)

    def test_une_hauteur_nulle_sans_source_reste_acceptee(self):
        """Non mesurée : il n'y a rien à tracer."""
        document = document_avec_batiments()
        del document['buildings'][1]['source']
        valider_document(document)

    def test_une_hauteur_negative_nomme_le_champ(self):
        document = document_avec_batiments()
        document['buildings'][0]['hauteurM'] = -3
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'buildings.0.hauteurM')

    def test_une_hauteur_a_zero_est_refusee(self):
        document = document_avec_batiments()
        document['buildings'][0]['hauteurM'] = 0
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'buildings.0.hauteurM')

    def test_un_batiment_sans_identifiant_est_refuse(self):
        document = document_avec_batiments()
        del document['buildings'][1]['id']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'buildings.1')
        self.assertIn('id', str(refus))

    def test_un_nombre_d_etages_decimal_est_refuse(self):
        document = document_avec_batiments()
        document['buildings'][0]['etages'] = 2.5
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'buildings.0.etages')
