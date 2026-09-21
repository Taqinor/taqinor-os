"""CALX86 — le contrat du CALQUE DE FOND calé (`underlay`) du document v2.

CE QUE CE FICHIER GARDE
-----------------------
Les calques `photo` et `plan` du panneau sont déclarés et affichés
(`frontend/src/features/calepinage/calques.js`) mais pilotent une liste VIDE
de couches MapLibre dans le builder (`apps/web/src/scripts/roofPro11/
mapDraw.ts`) : le calque de fond n'existe pas encore. L'analyseur de plan,
lui, rend un contour dans l'unité DU FICHIER et ne convertit JAMAIS en mètres
(`services/import_plan.py`), et le rangement de photo existe déjà
(`services/photos.py`). CALX86 pose la forme, avant les lanes UNDERLAY qui la
liront. Quatre promesses sont affirmées ici :

1. **La clé est ADDITIVE.** Un document v2 sans `underlay` reste valide —
   aucun fond, exactement l'atelier d'aujourd'hui ; l'`exemple` du schéma n'a
   pas bougé.
2. **AUCUNE échelle n'est déduite d'un fichier muet.** Un calage de `plan`
   sans `distanceReelleM` est REFUSÉ en nommant la clé ; aucune valeur n'est
   proposée par le schéma (D-CALX 7).
3. **Une photo ne reçoit PAS un second calage.** Elle est déjà calée à QUATRE
   coins par CAL53 (`PhotoSite.calage`,
   ``services/photos.py::calage_photo_site``) : un `kind: 'photo'` porteur
   d'un calage à deux points est REFUSÉ en nommant `calage`.
4. **Les refus sont prononcés par la porte d'import RÉELLE**
   (``services/io_layout.py::valider_document``), pas par une validation
   réécrite pour le test.

`EXEMPLE_PLAN` et `EXEMPLE_PHOTO` ci-dessous sont les deux fonds que les
lanes 3D (`apps/web`) liront TELS QUELS. Leurs nombres sont des valeurs
d'EXEMPLE : la distance réelle est une mesure SAISIE, pas une échelle
standard.

Run :
    python manage.py test apps.calepinage.tests.test_calx86_underlay
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

#: Un PLAN importé : sans échelle propre, donc calé à DEUX points avec une
#: distance réelle SAISIE et tracée. `pointsImage` est dans le repère du
#: fichier, jamais converti.
EXEMPLE_PLAN = {
    'kind': 'plan',
    'attachmentId': 3071,
    'opacite': 0.6,
    'calage': {
        'ancre': [[0.0, 0.0], [10.0, 0.0]],
        'pointsImage': [[120.0, 840.0], [1080.0, 840.0]],
        'distanceReelleM': 10.0,
        'rotationDeg': 0,
        'source': 'cote lue sur le plan',
    },
}

#: Une PHOTO de site : DÉJÀ calée à quatre coins par CAL53, donc AUCUN
#: `calage` ici — le fond lit `PhotoSite.calage`, et lui seul.
EXEMPLE_PHOTO = {
    'kind': 'photo',
    'photoSiteId': 918,
    'attachmentId': None,
    'opacite': 0.45,
}


def document_avec_plan():
    """L'exemple du schéma, augmenté du fond `plan` de CALX86."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['underlay'] = copy.deepcopy(EXEMPLE_PLAN)
    return document


def document_avec_photo():
    """L'exemple du schéma, augmenté du fond `photo` de CALX86."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['underlay'] = copy.deepcopy(EXEMPLE_PHOTO)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`underlay` est OPTIONNELLE : rien de ce qui existe ne bouge."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_pas_de_fond(self):
        """La preuve que le document historique n'a pas été réécrit."""
        self.assertNotIn('underlay', SCHEMA['exemple'])

    def test_un_document_sans_fond_reste_valide(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])
        valider_document(copy.deepcopy(SCHEMA['exemple']))

    def test_un_document_avec_un_plan_est_valide(self):
        self.assertEqual(erreurs(document_avec_plan()), [])

    def test_un_document_avec_une_photo_est_valide(self):
        self.assertEqual(erreurs(document_avec_photo()), [])

    def test_retirer_la_cle_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        for fabrique in (document_avec_plan, document_avec_photo):
            with self.subTest(fond=fabrique.__name__):
                document = fabrique()
                document.pop('underlay')
                self.assertEqual(document, SCHEMA['exemple'])


class DeuxGenresDeuxCalagesTest(SimpleTestCase):
    """Un plan se cale à deux points ; une photo est déjà calée."""

    def setUp(self):
        self.fond = SCHEMA['$defs']['underlay']
        self.calage = SCHEMA['$defs']['calageDeuxPoints']

    def test_le_genre_est_une_enumeration_fermee(self):
        self.assertEqual(self.fond['properties']['kind']['enum'],
                         ['plan', 'photo'])

    def test_le_plan_de_l_exemple_porte_son_calage(self):
        self.assertIn('calage', EXEMPLE_PLAN)
        self.assertEqual(len(EXEMPLE_PLAN['calage']['ancre']), 2)
        self.assertEqual(len(EXEMPLE_PLAN['calage']['pointsImage']), 2)

    def test_la_photo_de_l_exemple_ne_porte_aucun_calage(self):
        self.assertNotIn(
            'calage', EXEMPLE_PHOTO,
            'Une photo est DÉJÀ calée à quatre coins par CAL53 : un second '
            'calage serait une deuxième source de vérité.')
        self.assertIn('photoSiteId', EXEMPLE_PHOTO)

    def test_le_calage_exige_ses_quatre_valeurs(self):
        self.assertEqual(
            sorted(self.calage['required']),
            ['ancre', 'distanceReelleM', 'pointsImage', 'source'])

    def test_les_deux_points_sont_exactement_deux(self):
        for nom in ('ancre', 'pointsImage'):
            sous_schema = self.calage['properties'][nom]
            self.assertEqual(sous_schema['minItems'], 2)
            self.assertEqual(sous_schema['maxItems'], 2)

    def test_la_rotation_reste_facultative(self):
        self.assertNotIn('rotationDeg', self.calage['required'])


class AucuneEchelleDeduiteTest(SimpleTestCase):
    """Un fichier muet ne se met pas à l'échelle tout seul (D-CALX 7)."""

    def setUp(self):
        self.calage = SCHEMA['$defs']['calageDeuxPoints']
        self.fond = SCHEMA['$defs']['underlay']

    def test_aucune_distance_par_defaut(self):
        distance = self.calage['properties']['distanceReelleM']
        self.assertEqual(set(distance),
                         {'description', 'type', 'exclusiveMinimum'})
        self.assertEqual(distance['exclusiveMinimum'], 0)

    def test_aucune_valeur_par_defaut_nulle_part(self):
        for bloc in (self.calage['properties'], self.fond['properties']):
            for nom, sous_schema in bloc.items():
                for interdit in ('default', 'examples'):
                    self.assertNotIn(
                        interdit, sous_schema,
                        f'`{nom}` porte « {interdit} » : le schéma livrerait '
                        f'une échelle que personne n’a mesurée.')

    def test_la_provenance_de_la_distance_est_obligatoire(self):
        self.assertIn('source', self.calage['required'])
        self.assertEqual(self.calage['properties']['source']['minLength'], 1)

    def test_l_opacite_reste_bornee_et_sans_defaut(self):
        opacite = self.fond['properties']['opacite']
        self.assertEqual(opacite['minimum'], 0)
        self.assertEqual(opacite['maximum'], 1)
        self.assertNotIn('default', opacite)


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_les_deux_fonds_de_l_exemple_passent_la_porte(self):
        valider_document(document_avec_plan())
        valider_document(document_avec_photo())

    def test_un_calage_de_plan_sans_distance_nomme_la_cle(self):
        document = document_avec_plan()
        del document['underlay']['calage']['distanceReelleM']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'underlay.calage')
        self.assertIn('distanceReelleM', str(refus),
                      'Sans distance réelle le calage ne dit rien : le '
                      'message doit NOMMER la clé manquante.')

    def test_un_calage_de_plan_sans_provenance_nomme_la_cle(self):
        document = document_avec_plan()
        del document['underlay']['calage']['source']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'underlay.calage')
        self.assertIn('source', str(refus))

    def test_une_photo_porteuse_d_un_calage_nomme_la_cle_calage(self):
        document = document_avec_photo()
        document['underlay']['calage'] = copy.deepcopy(EXEMPLE_PLAN['calage'])
        refus = self._refus(document)
        self.assertEqual(
            refus.champ, 'underlay.calage',
            'Une photo lit son calage à quatre coins (CAL53) : le refus doit '
            'pointer EXACTEMENT la clé en trop.')

    def test_une_photo_sans_photo_site_est_refusee(self):
        document = document_avec_photo()
        del document['underlay']['photoSiteId']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'underlay')
        self.assertIn('photoSiteId', str(refus))

    def test_un_plan_sans_fichier_est_refuse(self):
        document = document_avec_plan()
        document['underlay']['attachmentId'] = None
        refus = self._refus(document)
        self.assertIn('attachmentId', refus.champ)

    def test_un_genre_inconnu_nomme_le_champ_kind(self):
        document = document_avec_plan()
        document['underlay']['kind'] = 'cadastre'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'underlay.kind')
        self.assertIn('cadastre', str(refus))

    def test_un_fond_sans_genre_est_refuse(self):
        document = document_avec_plan()
        del document['underlay']['kind']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'underlay')
        self.assertIn('kind', str(refus))

    def test_une_distance_a_zero_nomme_le_champ(self):
        document = document_avec_plan()
        document['underlay']['calage']['distanceReelleM'] = 0
        refus = self._refus(document)
        self.assertIn('distanceReelleM', refus.champ)

    def test_un_calage_a_trois_points_est_refuse(self):
        document = document_avec_plan()
        document['underlay']['calage']['ancre'].append([5.0, 5.0])
        refus = self._refus(document)
        self.assertIn('ancre', refus.champ)

    def test_une_opacite_hors_bornes_nomme_le_champ(self):
        document = document_avec_plan()
        document['underlay']['opacite'] = 1.5
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'underlay.opacite')

    def test_un_plan_sans_calage_reste_accepte(self):
        """Fond posé, pas encore calé : l'atelier le dira, pas le schéma."""
        document = document_avec_plan()
        del document['underlay']['calage']
        valider_document(document)
