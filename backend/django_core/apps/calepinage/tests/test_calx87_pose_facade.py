"""CALX87 — le contrat de la surface de pose « façade » et des appuis.

CE QUE CE FICHIER GARDE
-----------------------
`$defs/poseSurface.kind` n'admettait que `sol` (CAL89) et `ombriere`
(CAL91) : aucune occurrence de « façade » n'existait dans
`apps/web/src/scripts/roofPro11/`, `apps/web/src/lib/roofPro2.ts` ni le
schéma. Et `clearHeightM` donnait la hauteur LIBRE sous une ombrière sans
jamais dire ce qui tient au-dessus. CALX87 pose les deux formes manquantes.
Trois promesses sont affirmées ici :

1. **Tout est ADDITIF.** Un document existant se relit à l'identique :
   `sol` et `ombriere` restent ce qu'ils étaient, l'`exemple` du schéma n'a
   pas bougé, et les trois clés nouvelles sont facultatives.
2. **Une façade porte ses DEUX hauteurs, ou elle est REFUSÉE.** Sans
   `hauteurBasseM` ET `hauteurHauteM`, la façade n'a aucune étendue
   verticale, donc aucune surface posable ; le refus NOMME les clés et il est
   prononcé par la porte d'import RÉELLE
   (``services/io_layout.py::valider_document``).
3. **Aucune structure n'est calculée** (CAL89/CAL91) : `appuis` dit OÙ sont
   les poteaux et ce qu'ils mesurent, jamais ce qu'ils supportent — ni
   charge, ni matériau, ni prix, ni valeur par défaut (D-CALX 7).

`EXEMPLE_SURFACES` ci-dessous est le tableau que les lanes 3D (`apps/web`)
liront TEL QUEL : une `facade` bornée en hauteur et une `ombriere` avec ses
appuis. Ses nombres sont des valeurs d'EXEMPLE saisies.

Run :
    python manage.py test apps.calepinage.tests.test_calx87_pose_facade
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

#: Une FAÇADE bornée en hauteur (un mur n'est presque jamais posable sur
#: toute sa hauteur) et une OMBRIÈRE qui décrit enfin ses appuis.
EXEMPLE_SURFACES = [
    {
        'kind': 'facade',
        'id': 'ps-facade-1',
        'label': 'Mur sud (exemple)',
        'vertices': [[0, 0], [12, 0]],
        'hauteurBasseM': 3.0,
        'hauteurHauteM': 8.4,
        'rowAzimuthDeg': 180,
        'tiltDeg': 90,
        'areaM2': None,
        'terrainSlopeDeg': None,
    },
    {
        'kind': 'ombriere',
        'id': 'ps-ombriere-1',
        'label': 'Ombrière parking (exemple)',
        'vertices': [[20, 0], [32, 0], [32, 5], [20, 5]],
        'clearHeightM': 2.4,
        'flowAzimuthDeg': 180,
        'tiltDeg': 10,
        'appuis': {'pasM': 6.0, 'sectionM': 0.18},
    },
]


def document_avec_surfaces():
    """L'exemple du schéma, augmenté du fragment de CALX87."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['poseSurfaces'] = copy.deepcopy(EXEMPLE_SURFACES)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class ToutEstAdditifTest(SimpleTestCase):
    """Un document existant se relit à l'identique."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_aucune_surface_de_pose(self):
        """La preuve que le document historique n'a pas été réécrit."""
        self.assertNotIn('poseSurfaces', SCHEMA['exemple'])

    def test_un_document_sans_surface_reste_valide(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])

    def test_un_document_avec_facade_et_ombriere_est_valide(self):
        self.assertEqual(erreurs(document_avec_surfaces()), [])

    def test_les_deux_genres_historiques_restent_valides(self):
        """`sol` et `ombriere` sont ce qu'ils étaient avant CALX87."""
        for genre in ('sol', 'ombriere'):
            with self.subTest(kind=genre):
                document = copy.deepcopy(SCHEMA['exemple'])
                document['poseSurfaces'] = [{'kind': genre, 'id': 'ps-1'}]
                self.assertEqual(erreurs(document), [])
                valider_document(document)

    def test_retirer_la_cle_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_surfaces()
        document.pop('poseSurfaces')
        self.assertEqual(document, SCHEMA['exemple'])


class LesTroisGenresTest(SimpleTestCase):
    """`facade` rejoint `sol` et `ombriere` — et rien d'autre n'entre."""

    def setUp(self):
        self.surface = SCHEMA['$defs']['poseSurface']

    def test_l_enumeration_est_fermee_et_porte_les_trois(self):
        self.assertEqual(self.surface['properties']['kind']['enum'],
                         ['sol', 'ombriere', 'facade'])

    def test_l_exemple_exerce_la_facade_et_les_appuis(self):
        genres = {surface['kind'] for surface in EXEMPLE_SURFACES}
        self.assertEqual(genres, {'facade', 'ombriere'})
        ombriere = EXEMPLE_SURFACES[1]
        self.assertEqual(sorted(ombriere['appuis']), ['pasM', 'sectionM'])

    def test_les_deux_hauteurs_ne_se_deduisent_pas_l_une_de_l_autre(self):
        for nom in ('hauteurBasseM', 'hauteurHauteM'):
            sous_schema = self.surface['properties'][nom]
            for interdit in ('default', 'const', 'examples'):
                self.assertNotIn(
                    interdit, sous_schema,
                    f'`{nom}` porte « {interdit} » : le schéma livrerait une '
                    f'hauteur que personne n’a mesurée.')

    def test_un_genre_inconnu_est_refuse(self):
        document = document_avec_surfaces()
        document['poseSurfaces'][0]['kind'] = 'pergola'
        self.assertNotEqual(erreurs(document), [])


class AucuneStructureCalculeeTest(SimpleTestCase):
    """`appuis` décrit des appuis ; il ne dimensionne rien."""

    def setUp(self):
        self.appuis = SCHEMA['$defs']['appuisOmbriere']

    def test_deux_mesures_et_rien_d_autre(self):
        self.assertEqual(set(self.appuis['properties']),
                         {'pasM', 'sectionM'})

    def test_aucun_champ_de_charge_ni_de_prix(self):
        """La garde porte sur les CHAMPS, pas sur la prose qui les exclut."""
        for champ in self.appuis['properties']:
            for interdit in ('prix', 'marge', 'cout', 'charge', 'effort',
                             'contrainte', 'materiau'):
                self.assertNotIn(
                    interdit, champ.lower(),
                    f'Le champ « {champ} » dimensionnerait la structure : '
                    f'CAL89/CAL91 ne calculent aucune charge ici.')

    def test_aucune_valeur_par_defaut(self):
        for nom, sous_schema in self.appuis['properties'].items():
            for interdit in ('default', 'const', 'enum', 'examples'):
                self.assertNotIn(
                    interdit, sous_schema,
                    f'`{nom}` porte « {interdit} » : un entraxe vient d’une '
                    f'étude ou d’un relevé, jamais d’un contrat de données.')

    def test_une_mesure_absente_reste_null(self):
        for nom in ('pasM', 'sectionM'):
            self.assertIn('null', self.appuis['properties'][nom]['type'])

    def test_des_appuis_vides_restent_valides(self):
        document = document_avec_surfaces()
        document['poseSurfaces'][1]['appuis'] = {'pasM': None,
                                                 'sectionM': None}
        self.assertEqual(erreurs(document), [])


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_surfaces())

    def test_une_facade_sans_hauteur_basse_nomme_la_cle(self):
        document = document_avec_surfaces()
        del document['poseSurfaces'][0]['hauteurBasseM']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'poseSurfaces.0')
        self.assertIn('hauteurBasseM', str(refus))

    def test_une_facade_sans_hauteur_haute_nomme_la_cle(self):
        document = document_avec_surfaces()
        del document['poseSurfaces'][0]['hauteurHauteM']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'poseSurfaces.0')
        self.assertIn('hauteurHauteM', str(refus))

    def test_une_facade_sans_aucune_des_deux_est_refusee(self):
        document = document_avec_surfaces()
        del document['poseSurfaces'][0]['hauteurBasseM']
        del document['poseSurfaces'][0]['hauteurHauteM']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'poseSurfaces.0')

    def test_une_facade_a_hauteur_nulle_est_refusee(self):
        """« Non mesuré » ne se pave pas : `null` n'est pas une hauteur."""
        document = document_avec_surfaces()
        document['poseSurfaces'][0]['hauteurBasseM'] = None
        refus = self._refus(document)
        self.assertIn('hauteurBasseM', refus.champ)

    def test_une_ombriere_n_exige_aucune_hauteur_de_mur(self):
        document = document_avec_surfaces()
        ombriere = document['poseSurfaces'][1]
        self.assertNotIn('hauteurBasseM', ombriere)
        self.assertNotIn('hauteurHauteM', ombriere)
        valider_document(document)

    def test_un_entraxe_a_zero_nomme_le_champ(self):
        document = document_avec_surfaces()
        document['poseSurfaces'][1]['appuis']['pasM'] = 0
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'poseSurfaces.1.appuis.pasM')

    def test_une_hauteur_de_facade_negative_nomme_le_champ(self):
        document = document_avec_surfaces()
        document['poseSurfaces'][0]['hauteurHauteM'] = -2
        refus = self._refus(document)
        self.assertIn('hauteurHauteM', refus.champ)
