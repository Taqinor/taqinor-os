"""CALX201 — le contrat `electrical.equipements[]` du document v2.

CE QUE CE FICHIER GARDE
-----------------------
Un SCHÉMA et un ÉCHANTILLON, pas un service : l'atelier qui écrira ces
équipements arrive avec CALX219/CALX220, et les quatre consommateurs
(tronçons CALX224, schéma unifilaire CALX204, nomenclature, panneau
électrique) sont des lanes file-disjointes qui liront l'exemple TEL QUEL.
Ce qui peut — et doit — être affirmé aujourd'hui tient en quatre promesses :

1. **La clé est ADDITIVE.** Un document v2 sans `electrical` reste valide,
   l'`exemple` du schéma n'a pas bougé, et le même document avec la clé
   reste valide lui aussi.
2. **L'énumération des huit types est FERMÉE**, et l'exemple les exerce tous
   les huit (sinon la fixture de `electrique3d.test.ts` ne prouverait rien).
3. **Les refus NOMMENT le champ fautif**, et ils sont prononcés par la porte
   d'import RÉELLE (``services/io_layout.py::valider_document``), pas par une
   validation réécrite pour le test.
4. **Aucune grandeur électrique n'habite le document** : ni puissance, ni
   calibre, ni section, ni prix — toute caractéristique se lit sur la fiche
   produit (`produitId`, CALX60).

Aucune base de données, aucun réseau : deux fichiers JSON et `jsonschema`.

Run :
    python manage.py test apps.calepinage.tests.test_calx201_contrat_equipements
"""
from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase
from jsonschema import Draft202012Validator

from apps.calepinage.services.io_layout import (
    ImportLayoutRefuse, valider_document,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


SCHEMA = charger('roof_layout_v2.schema.json')
EQUIPEMENTS = charger('electrique_equipements.json')

#: Les huit organes que l'atelier sait poser — énumération FERMÉE (CALX201).
HUIT_TYPES = ['onduleur', 'coffret_dc', 'coffret_ac', 'compteur_production',
              'compteur_reseau', 'tgbt', 'batterie', 'parafoudre']

#: Les mots qui n'ont RIEN à faire dans une entrée d'équipement : une
#: grandeur électrique écrite ici serait une deuxième source de vérité en
#: face de la fiche produit (D-CALX 7, et « aucun seuil dans le code »).
INTERDITS = ('puissance', 'calibre', 'section', 'tension', 'courant',
             'prix', 'marge', 'kwc', 'kw', 'watt', 'ampere', 'volt')


def document_avec_equipements():
    """L'exemple du schéma, augmenté du fragment de CALX201."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document.update(copy.deepcopy(EQUIPEMENTS['exemple']))
    return document


class EnveloppeTest(SimpleTestCase):
    """L'échantillon porte l'enveloppe PACT10 et vise la bonne route."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, EQUIPEMENTS,
                          f'electrique_equipements.json : clé « {cle} » '
                          f'absente — check_api_shapes ne saurait pas le '
                          f'lire.')
        self.assertTrue(EQUIPEMENTS['endpoint'].strip())

    def test_la_route_visee_est_celle_du_document(self):
        self.assertEqual(EQUIPEMENTS['endpoint'], SCHEMA['endpoint'],
                         'Le fragment décrit une clé du document servi par '
                         'GET layout/ : il vise la MÊME route que le schéma.')

    def test_le_fragment_se_declare_partiel(self):
        self.assertEqual(EQUIPEMENTS['forme_serveur'], 'partielle',
                         "`exemple` est un fragment de `roof_layout`, pas le "
                         "corps complet de la réponse : la déclaration doit "
                         "le dire, sinon la garde lirait la vue.")


class CleAdditiveTest(SimpleTestCase):
    """`electrical` est OPTIONNELLE : rien de ce qui existe ne bouge."""

    def setUp(self):
        self.validateur = Draft202012Validator(SCHEMA)

    def _erreurs(self, document):
        return [(list(erreur.absolute_path), erreur.message)
                for erreur in self.validateur.iter_errors(document)]

    def test_le_schema_reste_bien_forme(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_pas_la_cle(self):
        """La preuve que le document historique n'a pas été réécrit."""
        self.assertNotIn(
            'electrical', SCHEMA['exemple'],
            "L'`exemple` du schéma est relu par quatre modules (import/"
            "export CAL216, aller-retour CALX28, non-régression ventes, "
            "étape d'ombrage proche) : CALX201 ne le touche pas.")

    def test_un_document_sans_la_cle_reste_valide(self):
        self.assertEqual(self._erreurs(SCHEMA['exemple']), [])
        self.assertEqual(self._erreurs({}), [])
        self.assertEqual(
            self._erreurs(EQUIPEMENTS['exemple_document_sans_electrical']),
            [])

    def test_un_document_avec_la_cle_est_valide(self):
        self.assertEqual(self._erreurs(document_avec_equipements()), [])

    def test_la_couche_vide_est_valide(self):
        self.assertEqual(self._erreurs(EQUIPEMENTS['exemple_vide']), [])

    def test_retirer_la_cle_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_equipements()
        document.pop('electrical')
        self.assertEqual(document, SCHEMA['exemple'])


class EnumerationFermeeTest(SimpleTestCase):
    """Les huit types, et rien d'autre ; les deux provenances, et rien d'autre."""

    def setUp(self):
        self.entree = SCHEMA['$defs']['equipementElectrique']

    def test_les_huit_types_sont_ceux_du_plan(self):
        self.assertEqual(self.entree['properties']['type']['enum'],
                         HUIT_TYPES)

    def test_les_deux_provenances_sont_fermees(self):
        self.assertEqual(self.entree['properties']['source']['enum'],
                         ['saisie', 'import'])

    def test_l_exemple_exerce_les_huit_types(self):
        """Sinon la fixture de `electrique3d.test.ts` ne prouverait rien."""
        poses = [entree['type']
                 for entree in EQUIPEMENTS['exemple']['electrical']
                 ['equipements']]
        self.assertEqual(sorted(poses), sorted(HUIT_TYPES))

    def test_l_exemple_exerce_les_deux_provenances(self):
        provenances = {entree['source']
                       for entree in EQUIPEMENTS['exemple']['electrical']
                       ['equipements']}
        self.assertEqual(provenances, {'saisie', 'import'})

    def test_les_identifiants_sont_uniques(self):
        """`cheminements[].de` / `.vers` les désignent (CALX202)."""
        poses = [entree['id']
                 for entree in EQUIPEMENTS['exemple']['electrical']
                 ['equipements']]
        self.assertEqual(sorted(poses), sorted(set(poses)))


class AucuneGrandeurElectriqueTest(SimpleTestCase):
    """Le document dit OÙ est l'organe, jamais ce qu'il vaut."""

    def test_aucun_champ_de_grandeur_dans_la_definition(self):
        champs = set(SCHEMA['$defs']['equipementElectrique']['properties'])
        self.assertEqual(
            champs,
            {'id', 'type', 'label', 'lng', 'lat', 'altitudeM',
             'rotationDeg', 'produitId', 'source'})
        for champ in champs:
            for interdit in INTERDITS:
                self.assertNotIn(
                    interdit, champ.lower(),
                    f'Le champ « {champ} » porte une grandeur électrique : '
                    f'elle se lit sur la fiche produit (produitId), pas dans '
                    f'le document.')

    def test_une_fiche_absente_n_est_pas_comblee(self):
        """`produitId: null` = organe sans fiche, jamais un produit par défaut."""
        sans_fiche = [entree
                      for entree in EQUIPEMENTS['exemple']['electrical']
                      ['equipements']
                      if entree['produitId'] is None]
        self.assertTrue(
            sans_fiche,
            "L'exemple doit montrer au moins un organe SANS fiche : c'est "
            "l'état qui fait omettre un calcul en nommant la fiche "
            'manquante.')

    def test_une_altitude_absente_n_est_pas_un_zero(self):
        hauteurs = [entree.get('altitudeM')
                    for entree in EQUIPEMENTS['exemple']['electrical']
                    ['equipements']]
        self.assertIn(None, hauteurs,
                      "L'exemple doit montrer une altitude NON RENSEIGNÉE "
                      '(null) — « au sol » et « non mesuré » ne sont pas le '
                      'même état.')


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_equipements())

    def test_un_type_hors_enumeration_nomme_le_champ_type(self):
        document = document_avec_equipements()
        document['electrical']['equipements'][0]['type'] = 'onduleur_hybride'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'electrical.equipements.0.type')
        self.assertIn('onduleur_hybride', str(refus))

    def test_une_entree_sans_lat_nomme_le_champ_manquant(self):
        document = document_avec_equipements()
        del document['electrical']['equipements'][0]['lat']
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'electrical.equipements.0')
        self.assertIn('lat', str(refus),
                      "Le message doit NOMMER le champ manquant : l'écran "
                      'concatène le chemin et ce nom pour pointer '
                      '« electrical.equipements.0.lat ».')

    def test_une_entree_sans_lng_est_refusee(self):
        document = document_avec_equipements()
        del document['electrical']['equipements'][0]['lng']
        self.assertIn('lng', str(self._refus(document)))

    def test_une_provenance_inconnue_est_refusee(self):
        document = document_avec_equipements()
        document['electrical']['equipements'][0]['source'] = 'devine'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'electrical.equipements.0.source')

    def test_les_deux_refus_de_l_echantillon_nomment_un_chemin(self):
        """Les textes affichés sont en français et pointent un champ."""
        for etat in ('refus_type_inconnu', 'refus_sans_position'):
            for champ, message in EQUIPEMENTS[etat].items():
                self.assertTrue(champ.startswith('electrical.equipements.'),
                                f'{etat} : « {champ} » ne pointe aucun champ '
                                f'du document.')
                self.assertTrue(message.strip().endswith('.'),
                                f'{etat} : le message doit être une phrase.')
