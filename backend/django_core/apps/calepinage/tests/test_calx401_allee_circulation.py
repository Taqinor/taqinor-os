"""CALX401 — le contrat de l'ALLÉE de circulation tracée du document v2.

CE QUE CE FICHIER GARDE
-----------------------
Une zone d'exclusion du v2 ne portait que `{id, label, nature, vertices,
setbackM, heightM}` : rien n'y distinguait un couloir de circulation d'une
zone quelconque. Et la seule allée que le module connaissait était une valeur
UNIFORME de réglage société (`services/degagements.py::allee_technique`,
`Parametres.allee_m`), jamais un passage dessiné sur le toit — alors qu'un
retrait de rive et un passage ne sont pas la même pièce. Quatre promesses
sont affirmées ici :

1. **Les trois clés sont ADDITIVES.** Une zone SANS `usage` se relit
   EXACTEMENT comme aujourd'hui ; l'`exemple` du schéma n'a pas bougé.
2. **`vertices` reste la géométrie qui fait foi.** `axe` garde le GESTE ; le
   couloir a été calculé depuis `axe` et `largeurM` au moment du tracé.
3. **Une allée porte son tracé et sa largeur, ou elle est REFUSÉE**, en
   nommant la clé, par la porte d'import RÉELLE
   (``services/io_layout.py::valider_document``).
4. **Le schéma ne livre AUCUNE largeur** : ni `default`, ni minimum
   réglementaire, ni suggestion chiffrée dans une description (D-CALX 7) —
   une largeur de passage se lit dans le texte qui s'applique au chantier.

`EXEMPLE_ZONES` ci-dessous est le tableau que les lanes 3D (`apps/web`)
liront TEL QUEL : une allée de deux points et une zone sans `usage`. Sa
largeur est une valeur d'EXEMPLE saisie, pas une prescription.

Run :
    python manage.py test apps.calepinage.tests.test_calx401_allee_circulation
"""
from __future__ import annotations

import copy
import json
import pathlib
import re

from django.test import SimpleTestCase

from apps.calepinage.services.io_layout import (
    ImportLayoutRefuse, valider_document,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
SCHEMA = json.loads((ECHANTILLONS / 'roof_layout_v2.schema.json')
                    .read_text(encoding='utf-8'))

#: Une zone d'exclusion ORDINAIRE (celle de l'exemple du schéma, inchangée)
#: et une ALLÉE tracée : deux points d'axe, une largeur saisie, et le couloir
#: déjà calculé dans `vertices` — c'est lui qui fait foi.
EXEMPLE_ZONES = [
    {
        'id': 'zx-1',
        'label': 'Bande technique',
        'nature': 'INTERDITE',
        'vertices': [[6, 0], [8, 0], [8, 1.5], [6, 1.5]],
        'setbackM': 0.3,
        'heightM': None,
    },
    {
        'id': 'zx-2',
        'label': 'Allée de circulation (exemple)',
        'nature': 'INTERDITE',
        'usage': 'circulation',
        'axe': [[0.5, 3.0], [9.5, 3.0]],
        'largeurM': 1.1,
        'vertices': [[0.5, 2.45], [9.5, 2.45], [9.5, 3.55], [0.5, 3.55]],
        'setbackM': 0,
        'heightM': None,
    },
]

#: Un nombre suivi d'une unité de longueur dans une description : ce serait
#: une largeur LIVRÉE par le schéma.
LARGEUR_LITTERALE = re.compile(r'\d+(?:[.,]\d+)?\s*(?:m\b|mètre|metre|cm\b)',
                               re.IGNORECASE)


def document_avec_allee():
    """L'exemple du schéma, augmenté du fragment de CALX401."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['exclusionZones'] = copy.deepcopy(EXEMPLE_ZONES)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`usage`, `axe` et `largeurM` sont OPTIONNELLES."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_aucune_allee(self):
        """La preuve que le document historique n'a pas été réécrit."""
        for zone in SCHEMA['exemple'].get('exclusionZones', []):
            self.assertNotIn('usage', zone)
            self.assertNotIn('axe', zone)
            self.assertNotIn('largeurM', zone)

    def test_une_zone_sans_usage_se_relit_exactement_comme_aujourd_hui(self):
        """Le cas d'aujourd'hui : aucun refus, aucune clé exigée."""
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        valider_document(copy.deepcopy(SCHEMA['exemple']))
        ordinaire = EXEMPLE_ZONES[0]
        self.assertEqual(ordinaire, SCHEMA['exemple']['exclusionZones'][0],
                         "La zone ordinaire de l'exemple est reprise SANS "
                         'modification : c’est elle qui prouve la '
                         'non-régression.')

    def test_un_document_avec_allee_est_valide(self):
        self.assertEqual(erreurs(document_avec_allee()), [])

    def test_retirer_l_allee_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_allee()
        document['exclusionZones'] = copy.deepcopy(
            SCHEMA['exemple']['exclusionZones'])
        self.assertEqual(document, SCHEMA['exemple'])


class LaGeometrieQuiFaitFoiTest(SimpleTestCase):
    """`vertices` prime ; `axe` garde le geste."""

    def setUp(self):
        self.allee = EXEMPLE_ZONES[1]

    def test_l_allee_porte_les_deux(self):
        self.assertEqual(len(self.allee['axe']), 2)
        self.assertEqual(len(self.allee['vertices']), 4,
                         'Le couloir est le POLYGONE calculé au moment du '
                         'tracé : c’est lui que les consommateurs lisent.')

    def test_le_schema_dit_laquelle_fait_foi(self):
        axe = SCHEMA['$defs']['exclusionZone']['properties']['axe']
        self.assertIn('vertices', axe['description'])
        self.assertIn('fait foi', axe['description'])

    def test_l_usage_est_une_enumeration_fermee(self):
        usage = SCHEMA['$defs']['exclusionZone']['properties']['usage']
        self.assertEqual(usage['enum'], ['circulation'])


class AucuneLargeurLivreeTest(SimpleTestCase):
    """Garde : le schéma ne porte AUCUNE largeur littérale (D-CALX 7)."""

    def setUp(self):
        self.zone = SCHEMA['$defs']['exclusionZone']

    def test_aucune_valeur_par_defaut_sur_la_largeur(self):
        largeur = self.zone['properties']['largeurM']
        self.assertEqual(set(largeur),
                         {'description', 'type', 'exclusiveMinimum'})
        self.assertEqual(largeur['exclusiveMinimum'], 0,
                         'Le seul nombre toléré est la borne « strictement '
                         'positif » — ce n’est pas une largeur, c’est une '
                         'nature.')

    def test_aucune_largeur_dans_les_descriptions_de_l_allee(self):
        for nom in ('usage', 'axe', 'largeurM'):
            texte = self.zone['properties'][nom]['description']
            trouve = LARGEUR_LITTERALE.search(texte)
            self.assertIsNone(
                trouve,
                f'La description de `{nom}` livre une longueur littérale '
                f'(« {trouve.group(0) if trouve else ""} ») : un chiffre écrit '
                f'là serait lu comme une prescription.')

    def test_aucune_largeur_dans_la_clause_conditionnelle(self):
        clause = json.dumps(self.zone['allOf'], ensure_ascii=False)
        self.assertIsNone(LARGEUR_LITTERALE.search(clause))


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_allee())

    def test_une_allee_sans_largeur_nomme_la_cle_largeur(self):
        document = document_avec_allee()
        del document['exclusionZones'][1]['largeurM']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'exclusionZones.1')
        self.assertIn('largeurM', str(refus))

    def test_une_allee_sans_axe_nomme_la_cle_axe(self):
        document = document_avec_allee()
        del document['exclusionZones'][1]['axe']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'exclusionZones.1')
        self.assertIn('axe', str(refus))

    def test_une_allee_a_un_seul_point_nomme_la_cle_axe(self):
        document = document_avec_allee()
        document['exclusionZones'][1]['axe'] = [[0.5, 3.0]]
        refus = self._refus(document)
        self.assertIn('axe', refus.champ)

    def test_une_largeur_a_zero_nomme_le_champ(self):
        document = document_avec_allee()
        document['exclusionZones'][1]['largeurM'] = 0
        refus = self._refus(document)
        self.assertIn('largeurM', refus.champ)

    def test_un_usage_inconnu_nomme_le_champ_usage(self):
        document = document_avec_allee()
        document['exclusionZones'][1]['usage'] = 'stockage'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'exclusionZones.1.usage')
        self.assertIn('stockage', str(refus))

    def test_une_zone_sans_usage_n_exige_ni_axe_ni_largeur(self):
        document = document_avec_allee()
        ordinaire = document['exclusionZones'][0]
        self.assertNotIn('axe', ordinaire)
        self.assertNotIn('largeurM', ordinaire)
        valider_document(document)
