"""CALX202 — le contrat `electrical.cheminements[]` du document v2.

CE QUE CE FICHIER GARDE
-----------------------
Le tracé des câbles n'existait nulle part : `entree_electrique['cheminement']`
n'est que trois scalaires saisis, et un tronçon coudé de 40 m y est compté
comme sa corde. Cette clé ajoute la topologie. Ce test tient ses trois
promesses, et NOMME le seul crochet que la tâche ne peut pas poser.

1. **La clé est ADDITIVE.** Document sans `electrical` toujours valide,
   `exemple` du schéma intact, document composé (pans + équipements +
   cheminements) valide.
2. **Moins de deux points ET aucune longueur saisie ⇒ REFUS qui nomme
   `points`.** La règle vit dans le schéma (`allOf`/`if`/`else`) et c'est la
   porte d'import RÉELLE (`services/io_layout.py::valider_document`) qui la
   prononce ici.
3. **Une référence morte est DÉCIDABLE depuis le seul document.** Aucun
   vocabulaire JSON Schema ne résout une référence croisée : la règle est
   posée ici, vérifiée sur l'exemple committé, et le CROCHET attendu côté
   serveur est nommé — `services/io_layout.py::valider_document`, qui lève
   déjà `ImportLayoutRefuse(champ=<chemin JSON>)`. Tant qu'il n'est pas
   posé, une référence morte passe la porte d'import : le dire est le but de
   ce fichier, le taire serait la panne.

Aucune base de données, aucun réseau : trois fichiers JSON et `jsonschema`.

Run :
    python manage.py test apps.calepinage.tests.test_calx202_contrat_cheminements
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
CHEMINEMENTS = charger('electrique_cheminements.json')

#: Les trois côtés électriques et les trois origines de longueur — fermés.
TROIS_COTES = ['dc', 'ac', 'terre']
TROIS_ORIGINES = ['plan', 'saisie', 'mixte']


def document_compose():
    """Les pans du schéma, les équipements de CALX201, les cheminements.

    C'est le document que les DEUX moitiés liront : les `de` / `vers` de
    l'exemple s'y résolvent RÉELLEMENT.
    """
    document = copy.deepcopy(SCHEMA['exemple'])
    document['electrical'] = {
        'equipements': copy.deepcopy(
            EQUIPEMENTS['exemple']['electrical']['equipements']),
        'cheminements': copy.deepcopy(
            CHEMINEMENTS['exemple']['electrical']['cheminements']),
    }
    return document


def references_du_document(document):
    """Les identifiants qu'un `de` / `vers` a le droit de désigner.

    Un `electrical.equipements[].id` (CALX201) ou un `zones[].id` (un pan,
    quand le tronçon part du champ de modules) — rien d'autre.
    """
    couche = document.get('electrical') or {}
    connus = {entree.get('id')
              for entree in (couche.get('equipements') or [])
              if isinstance(entree, dict)}
    connus |= {zone.get('id') for zone in (document.get('zones') or [])
               if isinstance(zone, dict)}
    return {identifiant for identifiant in connus if identifiant}


def references_mortes(document):
    """[(chemin JSON, référence morte)] — la règle que le schéma NE PEUT PAS
    porter.

    CROCHET ATTENDU : `services/io_layout.py::valider_document`, juste après
    `jsonschema.validate`, doit lever `ImportLayoutRefuse` sur le PREMIER
    chemin rendu ici. La fonction est pure : ni base, ni réseau, ni Django.
    """
    connus = references_du_document(document)
    couche = document.get('electrical') or {}
    mortes = []
    for rang, troncon in enumerate(couche.get('cheminements') or []):
        if not isinstance(troncon, dict):
            continue
        for bout in ('de', 'vers'):
            reference = troncon.get(bout)
            if reference not in connus:
                mortes.append(
                    (f'electrical.cheminements.{rang}.{bout}', reference))
    return mortes


class EnveloppeTest(SimpleTestCase):
    """L'échantillon porte l'enveloppe PACT10 et vise la bonne route."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CHEMINEMENTS,
                          f'electrique_cheminements.json : clé « {cle} » '
                          f'absente.')
        self.assertTrue(CHEMINEMENTS['endpoint'].strip())

    def test_la_route_visee_est_celle_du_document(self):
        self.assertEqual(CHEMINEMENTS['endpoint'], SCHEMA['endpoint'])
        self.assertEqual(CHEMINEMENTS['endpoint'], EQUIPEMENTS['endpoint'],
                         'Les deux fragments décrivent le MÊME document : '
                         'une route différente ferait diverger les deux '
                         'moitiés.')

    def test_le_fragment_se_declare_partiel(self):
        self.assertEqual(CHEMINEMENTS['forme_serveur'], 'partielle')


class CleAdditiveTest(SimpleTestCase):
    """`cheminements` est OPTIONNELLE : rien de ce qui existe ne bouge."""

    def setUp(self):
        self.validateur = Draft202012Validator(SCHEMA)

    def _erreurs(self, document):
        return [(list(erreur.absolute_path), erreur.message)
                for erreur in self.validateur.iter_errors(document)]

    def test_le_schema_reste_bien_forme(self):
        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_toujours_pas_la_cle(self):
        self.assertNotIn('electrical', SCHEMA['exemple'])

    def test_un_document_sans_la_cle_reste_valide(self):
        self.assertEqual(self._erreurs(SCHEMA['exemple']), [])
        self.assertEqual(self._erreurs({}), [])
        self.assertEqual(
            self._erreurs(CHEMINEMENTS['exemple_document_sans_electrical']),
            [])

    def test_le_document_compose_est_valide(self):
        self.assertEqual(self._erreurs(document_compose()), [])

    def test_la_couche_vide_est_valide(self):
        self.assertEqual(self._erreurs(CHEMINEMENTS['exemple_vide']), [])

    def test_retirer_la_cle_rend_le_document_de_depart(self):
        document = document_compose()
        document.pop('electrical')
        self.assertEqual(document, SCHEMA['exemple'])

    def test_les_equipements_restent_lisibles_sans_cheminements(self):
        """Les deux fragments sont indépendants : CALX201 vit sans CALX202."""
        document = document_compose()
        document['electrical'].pop('cheminements')
        self.assertEqual(self._erreurs(document), [])


class EnumerationsFermeesTest(SimpleTestCase):
    """Trois côtés, trois origines, et rien d'autre."""

    def setUp(self):
        self.entree = SCHEMA['$defs']['cheminementElectrique']

    def test_les_trois_cotes_sont_fermes(self):
        self.assertEqual(self.entree['properties']['cote']['enum'],
                         TROIS_COTES)

    def test_les_trois_origines_sont_fermees(self):
        self.assertEqual(self.entree['properties']['origine']['enum'],
                         TROIS_ORIGINES)

    def test_l_exemple_exerce_les_trois_cotes(self):
        poses = {troncon['cote'] for troncon
                 in CHEMINEMENTS['exemple']['electrical']['cheminements']}
        self.assertEqual(poses, set(TROIS_COTES))

    def test_l_exemple_exerce_les_trois_origines(self):
        """Ce sont les trois cas de test de CALX224 (plan, saisie, mixte)."""
        poses = {troncon['origine'] for troncon
                 in CHEMINEMENTS['exemple']['electrical']['cheminements']}
        self.assertEqual(poses, set(TROIS_ORIGINES))

    def test_aucune_longueur_n_est_ecrite_dans_le_troncon(self):
        """Le document dit PAR OÙ passe le câble, jamais ce qu'il vaut."""
        champs = set(self.entree['properties'])
        self.assertEqual(champs, {'id', 'cote', 'de', 'vers', 'points',
                                  'longueurSaisieM', 'origine'})
        for interdit in ('section', 'chute', 'calibre', 'ib', 'iz', 'prix'):
            self.assertNotIn(interdit, champs)

    def test_les_identifiants_de_troncon_sont_uniques(self):
        poses = [troncon['id'] for troncon
                 in CHEMINEMENTS['exemple']['electrical']['cheminements']]
        self.assertEqual(sorted(poses), sorted(set(poses)))


class LongueurMesurableTest(SimpleTestCase):
    """Moins de deux points ET aucune saisie ⇒ refus qui nomme `points`."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_compose_passe_la_porte(self):
        valider_document(document_compose())

    def test_un_troncon_sans_points_ni_longueur_nomme_points(self):
        document = document_compose()
        troncon = document['electrical']['cheminements'][3]
        self.assertEqual(troncon['id'], 'ch4')
        troncon.pop('longueurSaisieM')
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'electrical.cheminements.3.points')

    def test_un_seul_point_sans_longueur_est_refuse(self):
        document = document_compose()
        troncon = document['electrical']['cheminements'][0]
        troncon['points'] = troncon['points'][:1]
        self.assertEqual(self._refus(document).champ,
                         'electrical.cheminements.0.points')

    def test_une_longueur_saisie_dispense_du_trace(self):
        """`ch4` (traversée de mur) n'a AUCUN point et reste valide."""
        document = document_compose()
        self.assertEqual(document['electrical']['cheminements'][3]['points'],
                         [])
        valider_document(document)

    def test_une_longueur_nulle_ne_dispense_de_rien(self):
        """`null` = rien n'a été saisi, pas « zéro mètre »."""
        document = document_compose()
        troncon = document['electrical']['cheminements'][3]
        troncon['longueurSaisieM'] = None
        self.assertEqual(self._refus(document).champ,
                         'electrical.cheminements.3.points')

    def test_un_cote_inconnu_est_refuse(self):
        document = document_compose()
        document['electrical']['cheminements'][0]['cote'] = 'continu'
        self.assertEqual(self._refus(document).champ,
                         'electrical.cheminements.0.cote')

    def test_une_origine_inconnue_est_refusee(self):
        document = document_compose()
        document['electrical']['cheminements'][0]['origine'] = 'estimee'
        self.assertEqual(self._refus(document).champ,
                         'electrical.cheminements.0.origine')


class ReferenceMorteTest(SimpleTestCase):
    """La règle que le schéma ne peut pas porter — et son crochet nommé."""

    def test_l_exemple_committe_resout_toutes_ses_references(self):
        """Sinon les lanes qui le lisent partiraient d'un plan incohérent."""
        self.assertEqual(references_mortes(document_compose()), [])

    def test_chaque_bout_designe_un_equipement_ou_un_pan(self):
        document = document_compose()
        connus = references_du_document(document)
        self.assertIn('z1', connus, 'Un tronçon doit pouvoir partir d’un pan.')
        for troncon in document['electrical']['cheminements']:
            for bout in ('de', 'vers'):
                self.assertIn(troncon[bout], connus)

    def test_une_extremite_aval_morte_est_nommee(self):
        document = document_compose()
        document['electrical']['cheminements'][0]['vers'] = 'eq9'
        self.assertEqual(references_mortes(document),
                         [('electrical.cheminements.0.vers', 'eq9')])

    def test_une_extremite_amont_morte_est_nommee(self):
        document = document_compose()
        document['electrical']['cheminements'][2]['de'] = 'pan-supprime'
        self.assertEqual(references_mortes(document),
                         [('electrical.cheminements.2.de', 'pan-supprime')])

    def test_le_schema_seul_ne_voit_PAS_la_reference_morte(self):
        """Le constat qui justifie le crochet : la garde de schéma passe.

        CROCHET ATTENDU : `services/io_layout.py::valider_document` doit
        appeler la règle ci-dessus après `jsonschema.validate` et lever
        `ImportLayoutRefuse(champ=…)` sur la première référence morte. Tant
        qu'il n'est pas posé, ce document entre en base.
        """
        document = document_compose()
        document['electrical']['cheminements'][0]['vers'] = 'eq9'
        valider_document(document)
        self.assertTrue(references_mortes(document))

    def test_les_deux_refus_de_l_echantillon_nomment_un_chemin(self):
        for etat in ('refus_reference_morte', 'refus_sans_points_ni_longueur'):
            for champ, message in CHEMINEMENTS[etat].items():
                self.assertTrue(
                    champ.startswith('electrical.cheminements.'),
                    f'{etat} : « {champ} » ne pointe aucun champ du '
                    f'document.')
                self.assertTrue(message.strip().endswith('.'))
