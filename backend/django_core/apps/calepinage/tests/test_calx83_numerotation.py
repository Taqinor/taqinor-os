"""CALX83 — le contrat de NUMÉROTATION persistante des modules du v2.

CE QUE CE FICHIER GARDE
-----------------------
Aujourd'hui les seuls numéros affichés sont calculés à la volée depuis
l'index du tableau (`nº${i + 1}`, `apps/web/src/scripts/roofPro11/
shadingUi.ts`) : retirer un module renumérote tous ses voisins, et un rapport
d'ombrage imprimé la veille ne désigne plus rien. CALX83 fait voyager le
numéro DANS le document. Trois promesses sont affirmées ici :

1. **Les trois clés sont ADDITIVES.** Un document v2 sans `n`, sans `rangee`
   et sans `numerotation` reste valide, l'`exemple` du schéma n'a pas bougé,
   et le même document avec elles reste valide lui aussi.
2. **Le numéro est STABLE, donc TROUÉ.** Un module retiré laisse son numéro
   vacant ; le contrat n'exige AUCUNE suite continue, et le document
   d'exemple montre le trou.
3. **Deux modules d'un MÊME pan ne peuvent pas partager `n`.** `uniqueItems`
   compare des éléments entiers, pas une propriété d'objet : ce refus est
   donc prononcé par la porte d'import RÉELLE
   (``services/io_layout.py::valider_document``), et il NOMME le champ.

`EXEMPLE_MODULES_NUMEROTES` ci-dessous est le tableau que les lanes 3D
(`apps/web`) liront TEL QUEL. Ses coordonnées sont celles de l'exemple du
schéma, prolongées d'un module : ce sont des valeurs d'EXEMPLE.

Run :
    python manage.py test apps.calepinage.tests.test_calx83_numerotation
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

#: TROIS modules posés, numérotés 1, 2 et 4 : le module nº 3 a été RETIRÉ
#: après la pose et son numéro reste vacant — c'est exactement ce que
#: « numéro jamais réattribué » veut dire, et l'affichage par index
#: d'aujourd'hui ne sait pas le représenter.
EXEMPLE_MODULES_NUMEROTES = [
    {'cx': 0.0, 'cy': 0.0, 'n': 1, 'rangee': 'A'},
    {'cx': 1.2, 'cy': 0.0, 'n': 2, 'rangee': 'A'},
    {'cx': 0.0, 'cy': 1.8, 'n': 4, 'rangee': 'B'},
]

#: La convention SAISIE par l'utilisateur pour ce pan (valeurs d'exemple).
EXEMPLE_NUMEROTATION = {'prefixe': 'PV', 'depart': 1, 'sens': 'serpentin'}


def document_numerote():
    """L'exemple du schéma, augmenté du fragment de CALX83.

    L'accès solaire (CAL248) porte UNE valeur PAR module, dans le MÊME ordre
    et de la même longueur : le troisième module en reçoit une aussi, sans
    quoi le document se contredirait.
    """
    document = copy.deepcopy(SCHEMA['exemple'])
    geometrie = document['zones'][0]['geometry']
    geometrie['panels'] = copy.deepcopy(EXEMPLE_MODULES_NUMEROTES)
    geometrie['numerotation'] = copy.deepcopy(EXEMPLE_NUMEROTATION)
    geometrie['solarAccess']['values'] = [0.98, None, None]
    return document


def document_numerote_sans_module_ajoute():
    """Le MÊME pan qu'aujourd'hui, seulement numéroté.

    Sert à prouver l'additivité : retirer les trois clés rend le document de
    départ, sans qu'aucune autre valeur n'ait bougé.
    """
    document = copy.deepcopy(SCHEMA['exemple'])
    geometrie = document['zones'][0]['geometry']
    for place, module in enumerate(geometrie['panels']):
        module['n'] = place + 1
        module['rangee'] = 'A'
    geometrie['numerotation'] = copy.deepcopy(EXEMPLE_NUMEROTATION)
    return document


def validateur():
    """Le validateur 2020-12 — `jsonschema` importé en FONCTION-LOCALE."""
    from jsonschema import Draft202012Validator

    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(erreur.absolute_path), erreur.message)
            for erreur in validateur().iter_errors(document)]


class CleAdditiveTest(SimpleTestCase):
    """`n`, `rangee` et `numerotation` sont OPTIONNELLES."""

    def test_le_schema_reste_bien_forme(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_l_exemple_du_schema_ne_porte_aucun_numero(self):
        """La preuve que le document historique n'a pas été réécrit."""
        for zone in SCHEMA['exemple'].get('zones', []):
            geometrie = zone.get('geometry', {})
            self.assertNotIn('numerotation', geometrie)
            for module in geometrie.get('panels', []):
                self.assertNotIn('n', module)
                self.assertNotIn('rangee', module)

    def test_un_document_sans_numerotation_reste_valide(self):
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])

    def test_un_document_numerote_est_valide(self):
        self.assertEqual(erreurs(document_numerote()), [])
        self.assertEqual(erreurs(document_numerote_sans_module_ajoute()), [])

    def test_retirer_les_cles_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_numerote_sans_module_ajoute()
        geometrie = document['zones'][0]['geometry']
        geometrie.pop('numerotation')
        for module in geometrie['panels']:
            module.pop('n')
            module.pop('rangee')
        self.assertEqual(document, SCHEMA['exemple'])


class NumeroStableDoncTroueTest(SimpleTestCase):
    """Un module retiré laisse son numéro vacant — c'est le but."""

    def setUp(self):
        self.modules = document_numerote()['zones'][0]['geometry']['panels']

    def test_l_exemple_porte_un_trou(self):
        numeros = [module['n'] for module in self.modules]
        self.assertEqual(numeros, [1, 2, 4])
        self.assertNotIn(
            3, numeros,
            "Sans TROU, l'exemple ne prouverait pas ce que CALX83 apporte : "
            "un numéro attribué à la pose et JAMAIS réattribué.")

    def test_le_schema_n_exige_aucune_suite_continue(self):
        """Le contrat porte sur l'unicité, pas sur la continuité."""
        module = SCHEMA['$defs']['panel']['properties']['n']
        self.assertEqual(module['type'], 'integer')
        self.assertEqual(module['minimum'], 1)
        for interdit in ('default', 'const', 'enum', 'maximum'):
            self.assertNotIn(interdit, module)

    def test_la_rangee_est_une_etiquette(self):
        etiquettes = [module['rangee'] for module in self.modules]
        self.assertEqual(etiquettes, ['A', 'A', 'B'])
        self.assertEqual(
            SCHEMA['$defs']['panel']['properties']['rangee']['type'],
            'string')

    def test_l_acces_solaire_reste_de_la_meme_longueur(self):
        """CAL248 : une valeur PAR module, dans le MÊME ordre."""
        geometrie = document_numerote()['zones'][0]['geometry']
        self.assertEqual(len(geometrie['solarAccess']['values']),
                         len(geometrie['panels']))


class ConventionSaisieTest(SimpleTestCase):
    """`numerotation` DÉCRIT un choix ; elle ne renumérote rien."""

    def setUp(self):
        self.convention = SCHEMA['$defs']['numerotationPan']

    def test_aucune_cle_n_est_obligatoire(self):
        self.assertNotIn('required', self.convention)

    def test_le_sens_est_une_enumeration_fermee(self):
        self.assertEqual(self.convention['properties']['sens']['enum'],
                         ['ligne', 'serpentin'])

    def test_aucune_valeur_par_defaut(self):
        for nom, sous_schema in self.convention['properties'].items():
            for interdit in ('default', 'const', 'examples'):
                self.assertNotIn(
                    interdit, sous_schema,
                    f'`{nom}` porte « {interdit} » : le schéma imposerait une '
                    f'convention que personne n’a choisie.')

    def test_un_sens_inconnu_est_refuse(self):
        document = document_numerote()
        document['zones'][0]['geometry']['numerotation']['sens'] = 'diagonale'
        self.assertNotEqual(erreurs(document), [])


class RefusNommeLeChampTest(SimpleTestCase):
    """C'est la porte d'import RÉELLE qui refuse, et elle nomme le champ."""

    def _refus(self, document):
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(document)
        return capture.exception

    def test_le_document_de_l_exemple_passe_la_porte(self):
        valider_document(document_numerote())

    def test_deux_modules_d_un_meme_pan_ne_partagent_pas_un_numero(self):
        document = document_numerote()
        document['zones'][0]['geometry']['panels'][2]['n'] = 1
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.geometry.panels.2.n')
        self.assertIn('zones.0.geometry.panels.0.n', str(refus),
                      "Le message doit dire QUEL autre module porte déjà ce "
                      "numéro, sinon l'écran ne sait pas où envoyer l'œil.")

    def test_deux_pans_peuvent_porter_le_meme_numero(self):
        """L'unicité est par PAN : un site multi-pans a plusieurs « nº 1 »."""
        document = document_numerote()
        second = copy.deepcopy(document['zones'][0])
        second['id'] = f"{second['id']}-bis"
        document['zones'].append(second)
        valider_document(document)

    def test_un_numero_a_zero_nomme_le_champ(self):
        document = document_numerote()
        document['zones'][0]['geometry']['panels'][0]['n'] = 0
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.geometry.panels.0.n')

    def test_un_numero_decimal_est_refuse(self):
        document = document_numerote()
        document['zones'][0]['geometry']['panels'][0]['n'] = 1.5
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.geometry.panels.0.n')

    def test_une_rangee_vide_est_refusee(self):
        document = document_numerote()
        document['zones'][0]['geometry']['panels'][0]['rangee'] = ''
        refus = self._refus(document)
        self.assertEqual(refus.champ, 'zones.0.geometry.panels.0.rangee')

    def test_un_document_sans_numero_passe_la_porte(self):
        """Le cas d'aujourd'hui : aucun `n`, donc aucun doublon possible."""
        valider_document(copy.deepcopy(SCHEMA['exemple']))
