"""CALX81 — le contrat `zones[].edges[].retraitM` + `manuel` du document v2.

CE QUE CE FICHIER GARDE
-----------------------
Un SCHÉMA, pas un service. L'atelier qui écrira un retrait PAR ARÊTE arrive
plus tard dans le lot 2 (lane EDGES) ; ce qui peut — et doit — être affirmé
aujourd'hui tient en trois promesses :

1. **La clé est ADDITIVE.** Un document v2 sans `retraitM` reste valide,
   l'`exemple` du schéma n'a pas bougé (sept modules le relisent), et le même
   document avec la clé reste valide lui aussi.
2. **Aucune valeur n'est proposée.** Le schéma ne porte ni `default` ni
   largeur littérale : un retrait non saisi est ABSENT (D-CALX 7), et le
   retrait de CATÉGORIE (`setbacksM`, CAL76) continue de s'appliquer seul.
3. **Les refus NOMMENT le champ**, et ils sont prononcés par la porte d'import
   RÉELLE (``services/io_layout.py::valider_document``), pas par une
   validation réécrite pour le test.

`EXEMPLE_ARETES` ci-dessous est le document que les lanes 3D (`apps/web`)
liront TEL QUEL pour savoir ce qu'elles doivent écrire : ses valeurs sont
PLAUSIBLES et déclarées comme telles, aucune n'est une donnée d'ingénierie.

Aucune base de données, aucun réseau : un fichier JSON et `jsonschema`
(importé EN FONCTION-LOCALE, comme ``services/io_layout.py``, parce que la
bibliothèque n'arrive que TRANSITIVEMENT par `drf-spectacular` et n'est
épinglée nulle part).

Run :
    python manage.py test apps.calepinage.tests.test_calx81_arete_retrait
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

#: Les arêtes que le document sait porter depuis CALX81 : un type déduit
#: sans retrait propre, et une arête CORRIGÉE À LA MAIN qui porte son propre
#: retrait. Les deux valeurs de retrait sont des valeurs d'EXEMPLE, saisies
#: dans l'atelier par un humain — le schéma n'en propose aucune.
EXEMPLE_ARETES = [
    {'index': 0, 'type': 'faitage'},
    {'index': 1, 'type': 'rive', 'manuel': True, 'retraitM': 0.9},
    {'index': 2, 'type': 'egout', 'retraitM': 0.4},
]


def document_avec_retraits():
    """L'exemple du schéma, augmenté du fragment de CALX81."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['zones'][0]['edges'] = copy.deepcopy(EXEMPLE_ARETES)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`retraitM` est OPTIONNELLE : rien de ce qui existe ne bouge."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_reste_conforme(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])

    def test_l_exemple_du_schema_ne_porte_aucun_retrait_par_arete(self):
        """La preuve que le document historique n'a pas été réécrit."""
        for zone in SCHEMA['exemple'].get('zones', []):
            for arete in zone.get('edges', []):
                self.assertNotIn(
                    'retraitM', arete,
                    "L'`exemple` du schéma est relu par sept modules "
                    '(import/export CAL216, aller-retour CALX28, ombrage '
                    'proche, non-régression ventes, zones.json, '
                    'lead_layout_public.json) : CALX81 ne le touche pas.')

    def test_un_document_sans_retrait_par_arete_reste_valide(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])
        sans_retrait = document_avec_retraits()
        for arete in sans_retrait['zones'][0]['edges']:
            arete.pop('retraitM', None)
        self.assertEqual(erreurs(sans_retrait), [])

    def test_un_document_avec_retrait_par_arete_est_valide(self):
        self.assertEqual(erreurs(document_avec_retraits()), [])

    def test_retirer_la_cle_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_retraits()
        document['zones'][0]['edges'] = copy.deepcopy(
            SCHEMA['exemple']['zones'][0].get('edges', []))
        self.assertEqual(document, SCHEMA['exemple'])


class AucuneValeurProposeeTest(SimpleTestCase):
    """Le schéma décrit une FORME ; il ne livre aucun retrait (D-CALX 7)."""

    def setUp(self):
        self.arete = SCHEMA['$defs']['edge']['properties']

    def test_retrait_declare_sans_valeur_par_defaut(self):
        retrait = self.arete['retraitM']
        self.assertEqual(retrait['type'], 'number')
        self.assertEqual(retrait['minimum'], 0)
        for interdit in ('default', 'const', 'enum', 'examples'):
            self.assertNotIn(
                interdit, retrait,
                f'`retraitM` porte « {interdit} » : le schéma livrerait un '
                f'retrait que personne n’a mesuré.')

    def test_le_drapeau_manuel_dit_qui_a_ecrit_le_type(self):
        self.assertEqual(self.arete['manuel']['type'], 'boolean')
        self.assertIn('UTILISATEUR', self.arete['manuel']['description'])


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_avec_retraits())

    def test_un_retrait_negatif_nomme_le_champ(self):
        document = document_avec_retraits()
        document['zones'][0]['edges'][1]['retraitM'] = -1
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.edges.1.retraitM')
        self.assertIn('-1', str(refus))

    def test_un_retrait_qui_n_est_pas_un_nombre_est_refuse(self):
        document = document_avec_retraits()
        document['zones'][0]['edges'][1]['retraitM'] = '0,9'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.edges.1.retraitM')

    def test_un_drapeau_manuel_qui_n_est_pas_booleen_est_refuse(self):
        document = document_avec_retraits()
        document['zones'][0]['edges'][1]['manuel'] = 'oui'
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.edges.1.manuel')
