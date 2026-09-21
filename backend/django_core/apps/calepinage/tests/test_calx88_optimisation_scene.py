"""CALX88 — le contrat `optimisation` + `scene` du document v2.

CE QUE CE FICHIER GARDE
-----------------------
Aujourd'hui l'objectif du balayage est FIGÉ dans un comparateur unique qui
classe l'énergie annuelle posée d'abord
(`apps/web/src/lib/estimatorBrainV6.ts::betterMatrixV6`), la priorité de
remplissage CAL83 est du code SANS APPELANT
(`apps/web/src/scripts/roofPro11/optimizer.ts`, `PRIORITES_REMPLISSAGE` /
`departagerRemplissage`), et le soleil de scène est une bascule binaire
hiver/été dont ni `ctx.sunDay` ni `ctx.sunHour` n'apparaissent dans
`serializeLayout` : rouvrir le document perdait l'instant choisi, et l'ombre
montrée changeait sous les yeux du client. CALX88 fait voyager l'intention.
Quatre promesses sont affirmées ici :

1. **Les deux clés sont ADDITIVES.** Un document v2 sans `optimisation` et
   sans `scene` reste valide — objectif d'aujourd'hui, aucune priorité, aucun
   seuil, instant par défaut de la scène ; l'`exemple` du schéma n'a pas bougé.
2. **Les énumérations sont FERMÉES.** Une `cible` inconnue est REFUSÉE en
   nommant le champ, par la porte d'import RÉELLE
   (``services/io_layout.py::valider_document``) : un objectif sans
   comparateur ne classerait rien. `priorite` reprend EXACTEMENT les
   identifiants de `PRIORITES_REMPLISSAGE`.
3. **Aucun seuil n'est proposé.** `seuilAccesSolaire` vaut `null` par
   défaut d'information — un seuil d'acceptation est une décision
   commerciale, jamais une constante de contrat (D-CALX 7).
4. **`scene` est un POINT DE VUE, pas une donnée d'ingénierie.** Aucun
   calcul de production ni de perte n'en dépend.

`EXEMPLE_OPTIMISATION` et `EXEMPLE_SCENE` ci-dessous sont ce que les lanes 3D
(`apps/web`) liront TEL QUEL. Le jour du soleil y est volontairement HORS
solstice, sinon l'exemple ne prouverait pas que l'instant voyage.

Run :
    python manage.py test apps.calepinage.tests.test_calx88_optimisation_scene
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

#: Les identifiants de `PRIORITES_REMPLISSAGE` (CAL83), relus sur
#: `apps/web/src/scripts/roofPro11/optimizer.ts` — le contrat ne doit pas en
#: inventer un septième.
PRIORITES_REMPLISSAGE = ['aucune', 'faitage', 'egout', 'rive-debut',
                         'rive-fin', 'ensoleillement']

#: Les cinq objectifs nommés par CALX88.
CIBLES = ['compte', 'kwc', 'energie', 'ombrage', 'faitage']

#: Le jour du solstice d'hiver, celui que la scène affiche quand personne
#: n'a bougé la bascule (`WINTER_SOLSTICE_DAY`,
#: `apps/web/src/scripts/roofPro11/viewerFullBoot.ts`). L'exemple s'en
#: éloigne EXPRÈS.
JOUR_SOLSTICE_HIVER = 355

#: Une demande d'EXEMPLE : poser le plus de modules, en les collant au
#: faîtage, sans seuil d'accès solaire.
EXEMPLE_OPTIMISATION = {
    'cible': 'compte',
    'priorite': 'faitage',
    'seuilAccesSolaire': None,
}

#: Un instant d'EXEMPLE, hors solstice : c'est ce que le client voyait.
EXEMPLE_SCENE = {'sunDay': 172, 'sunHour': 14.5}


def document_avec_choix():
    """L'exemple du schéma, augmenté des deux fragments de CALX88."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['optimisation'] = copy.deepcopy(EXEMPLE_OPTIMISATION)
    document['scene'] = copy.deepcopy(EXEMPLE_SCENE)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`optimisation` et `scene` sont OPTIONNELLES."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_aucun_choix(self):
        """La preuve que le document historique n'a pas été réécrit."""
        self.assertNotIn('optimisation', SCHEMA['exemple'])
        self.assertNotIn('scene', SCHEMA['exemple'])

    def test_un_document_sans_optimisation_reste_accepte(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])
        valider_document(copy.deepcopy(SCHEMA['exemple']))

    def test_un_document_avec_les_deux_cles_est_valide(self):
        self.assertEqual(erreurs(document_avec_choix()), [])

    def test_chacune_des_deux_cles_vit_sans_l_autre(self):
        for cle, fragment in (('optimisation', EXEMPLE_OPTIMISATION),
                              ('scene', EXEMPLE_SCENE)):
            with self.subTest(cle=cle):
                document = copy.deepcopy(SCHEMA['exemple'])
                document[cle] = copy.deepcopy(fragment)
                self.assertEqual(erreurs(document), [])

    def test_aucune_sous_cle_n_est_obligatoire(self):
        document = copy.deepcopy(SCHEMA['exemple'])
        document['optimisation'] = {}
        document['scene'] = {}
        self.assertEqual(erreurs(document), [])

    def test_retirer_les_cles_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_choix()
        document.pop('optimisation')
        document.pop('scene')
        self.assertEqual(document, SCHEMA['exemple'])


class EnumerationsFermeesTest(SimpleTestCase):
    """Les cinq cibles, les six priorités — et rien d'autre."""

    def setUp(self):
        self.optimisation = SCHEMA['$defs']['optimisation']['properties']

    def test_les_cinq_cibles_sont_celles_du_plan(self):
        self.assertEqual(self.optimisation['cible']['enum'], CIBLES)

    def test_les_priorites_reprennent_celles_de_l_optimiseur(self):
        self.assertEqual(self.optimisation['priorite']['enum'],
                         PRIORITES_REMPLISSAGE,
                         'Le contrat ne doit pas inventer une priorité que '
                         '`PRIORITES_REMPLISSAGE` ne connaît pas.')

    def test_l_exemple_porte_une_cible(self):
        self.assertIn(EXEMPLE_OPTIMISATION['cible'], CIBLES)

    def test_chaque_cible_de_l_enumeration_est_acceptee(self):
        for cible in CIBLES:
            with self.subTest(cible=cible):
                document = document_avec_choix()
                document['optimisation']['cible'] = cible
                self.assertEqual(erreurs(document), [])

    def test_chaque_priorite_de_l_enumeration_est_acceptee(self):
        for priorite in PRIORITES_REMPLISSAGE:
            with self.subTest(priorite=priorite):
                document = document_avec_choix()
                document['optimisation']['priorite'] = priorite
                self.assertEqual(erreurs(document), [])


class AucunSeuilProposeTest(SimpleTestCase):
    """Un seuil d'acceptation est une décision, pas une constante."""

    def setUp(self):
        self.optimisation = SCHEMA['$defs']['optimisation']['properties']

    def test_le_seuil_accepte_null(self):
        seuil = self.optimisation['seuilAccesSolaire']
        self.assertIn('null', seuil['type'])
        self.assertEqual(seuil['minimum'], 0)
        self.assertEqual(seuil['maximum'], 1)

    def test_aucune_valeur_par_defaut_nulle_part(self):
        for bloc in (SCHEMA['$defs']['optimisation']['properties'],
                     SCHEMA['$defs']['scene']['properties']):
            for nom, sous_schema in bloc.items():
                for interdit in ('default', 'const', 'examples'):
                    self.assertNotIn(
                        interdit, sous_schema,
                        f'`{nom}` porte « {interdit} » : le schéma '
                        f'déciderait à la place de l’utilisateur.')

    def test_l_exemple_ne_pose_aucun_seuil(self):
        self.assertIsNone(EXEMPLE_OPTIMISATION['seuilAccesSolaire'])


class LeSoleilDeSceneVoyageTest(SimpleTestCase):
    """L'instant affiché survit au rechargement — et à rien d'autre."""

    def test_l_exemple_est_hors_solstice(self):
        self.assertNotEqual(
            EXEMPLE_SCENE['sunDay'], JOUR_SOLSTICE_HIVER,
            "Sur le jour par défaut, l'exemple ne prouverait pas que "
            "l'instant choisi voyage dans le document.")

    def test_le_jour_est_borne_sur_l_annee(self):
        jour = SCHEMA['$defs']['scene']['properties']['sunDay']
        self.assertEqual(jour['type'], 'integer')
        self.assertEqual((jour['minimum'], jour['maximum']), (1, 366))

    def test_l_heure_est_bornee_sur_la_journee(self):
        heure = SCHEMA['$defs']['scene']['properties']['sunHour']
        self.assertEqual((heure['minimum'], heure['maximum']), (0, 24))

    def test_la_scene_ne_porte_que_l_instant(self):
        self.assertEqual(set(SCHEMA['$defs']['scene']['properties']),
                         {'sunDay', 'sunHour'})


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_choix())

    def test_une_cible_inconnue_nomme_le_champ_cible(self):
        document = document_avec_choix()
        document['optimisation']['cible'] = 'rentabilite'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'optimisation.cible')
        self.assertIn('rentabilite', str(refus))

    def test_une_priorite_inconnue_nomme_le_champ_priorite(self):
        document = document_avec_choix()
        document['optimisation']['priorite'] = 'centre'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'optimisation.priorite')

    def test_un_seuil_hors_bornes_nomme_le_champ(self):
        document = document_avec_choix()
        document['optimisation']['seuilAccesSolaire'] = 1.4
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'optimisation.seuilAccesSolaire')

    def test_un_jour_hors_annee_nomme_le_champ(self):
        document = document_avec_choix()
        document['scene']['sunDay'] = 400
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'scene.sunDay')

    def test_un_jour_a_zero_est_refuse(self):
        document = document_avec_choix()
        document['scene']['sunDay'] = 0
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'scene.sunDay')

    def test_une_heure_hors_journee_nomme_le_champ(self):
        document = document_avec_choix()
        document['scene']['sunHour'] = 25
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'scene.sunHour')

    def test_un_jour_decimal_est_refuse(self):
        document = document_avec_choix()
        document['scene']['sunDay'] = 172.5
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'scene.sunDay')
