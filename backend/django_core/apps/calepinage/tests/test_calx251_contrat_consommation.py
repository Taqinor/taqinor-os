"""CALX251 — le contrat `consumption` du document `roof_layout` v2.

CE QUE CE FICHIER GARDE
------------------------
`serializeLayout` (`apps/web/src/scripts/roofPro11/prefill.ts:556`) n'émettait
AUCUNE des six clés de consommation de `Ctx` (`consCurve`, `consAppliances`,
`consSeasonal`, `consSummerFactor`, `consWinterFactor`, `consHandEdited` —
`apps/web/src/scripts/roofPro11/context.ts:313-329`) : le schéma ne portait que
`billKwh`. CALX251 déclare l'objet racine OPTIONNEL `consumption` qui les porte —
CALX253 l'émet depuis `serializeLayout`, CALX254 le relit dans
`hydrateFromLead`/`hydrateFromDevis` (les deux côté `apps/web`, hors du périmètre
de ce fichier). PACT10 : le contrat part SEUL sur `main`, avant elles.

Deux promesses sont affirmées ici (le Done littéral de CALX251) :

1. **Additif.** Un document v2 SANS `consumption` reste valide — l'`exemple` du
   schéma n'a d'ailleurs PAS bougé (`serializeLayout` n'émet ce bloc que lorsque
   l'utilisateur a réellement touché le panneau « Affiner ma consommation » ;
   un `Ctx` vierge ne l'émet jamais, CALX253) — et le même document AVEC la clé
   reste valide lui aussi.
2. **Le schéma est bien formé et l'`exemple` committé valide contre lui.**

`courbe24`/`methode`/`source` voyagent TOUJOURS ensemble (un producteur qui émet
le bloc les émet tous les trois) ; `saisons` (W95) et `appareils` sont chacun
OMIS quand ils n'apportent rien — jamais une valeur inventée (D-CALX 7).

Fonction PURE : ce test n'a besoin d'AUCUNE base de données ni d'aucun import
Django — seul `jsonschema` lit le fichier de contrat committé.

Run :
    cd backend/django_core && python -m pytest apps/calepinage/tests/test_calx251_contrat_consommation.py -q
"""
from __future__ import annotations

import copy
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
SCHEMA = json.loads((ECHANTILLONS / 'roof_layout_v2.schema.json')
                    .read_text(encoding='utf-8'))

#: Un bloc `consumption` d'EXEMPLE, réellement conforme au schéma — courbe
#: éditée à la main (`methode: 'courbe'`), modulation saisonnière W95 activée,
#: deux appareils. Ses nombres sont des valeurs d'EXEMPLE (D-CALX 7), jamais
#: des défauts.
EXEMPLE_CONSUMPTION = {
    'courbe24': [0.3] * 24,
    'saisons': {'ete': 1.4, 'hiver': 0.8},
    'appareils': [
        {
            'kind': 'clim', 'label': 'Climatisation', 'dailyKwh': 8.04,
            'startHour': 13, 'endHour': 23, 'billing': 'onTop',
        },
        {
            'kind': 'frigo', 'label': 'Réfrigérateur / congélateur',
            'dailyKwh': 1.5, 'startHour': 0, 'endHour': 24, 'billing': 'inBill',
        },
    ],
    'methode': 'courbe',
    'source': {'origine': 'atelier', 'saisi_le': '2026-09-23T10:00:00Z'},
}


def document_avec_consumption():
    """L'exemple du schéma, augmenté du fragment CALX251."""
    document = copy.deepcopy(SCHEMA['exemple'])
    document['consumption'] = copy.deepcopy(EXEMPLE_CONSUMPTION)
    return document


def validateur():
    """Le validateur 2020-12 — même millésime que `$schema` du fichier."""
    return Draft202012Validator(SCHEMA)


def erreurs(document):
    return [(list(e.absolute_path), e.message)
            for e in validateur().iter_errors(document)]


class SchemaBienFormeTest(unittest.TestCase):
    def test_le_schema_reste_bien_forme(self):
        Draft202012Validator.check_schema(SCHEMA)


class CleAdditiveTest(unittest.TestCase):
    """`consumption` est OPTIONNELLE : rien de ce qui existe ne bouge."""

    def test_l_exemple_du_schema_ne_porte_pas_la_consommation(self):
        """La preuve que le document historique n'a pas été réécrit —
        `serializeLayout` n'émet ce bloc que lorsque l'atelier a réellement
        été touché (CALX253)."""
        self.assertNotIn('consumption', SCHEMA['exemple'])

    def test_l_exemple_du_fichier_valide_contre_le_schema(self):
        """Done CALX251 : « l'exemple du fichier valide contre le schéma »."""
        self.assertEqual(erreurs(SCHEMA['exemple']), [])

    def test_un_document_v2_sans_consumption_reste_valide(self):
        """Done CALX251 : « un document v2 SANS consumption reste valide »."""
        self.assertEqual(erreurs(SCHEMA['exemple']), [])
        self.assertEqual(erreurs({}), [])
        self.assertEqual(erreurs({'version': 2, 'zones': []}), [])

    def test_un_document_avec_consumption_est_valide(self):
        self.assertEqual(erreurs(document_avec_consumption()), [])

    def test_retirer_la_cle_rend_le_document_de_depart(self):
        """Définition opérationnelle d'« additif » : rien d'autre ne change."""
        document = document_avec_consumption()
        document.pop('consumption')
        self.assertEqual(document, SCHEMA['exemple'])


class FormeDuBlocTest(unittest.TestCase):
    """`courbe24`/`methode`/`source` voyagent TOUJOURS ensemble (CALX253) ;
    `saisons`/`appareils` sont chacun omis quand ils n'apportent rien."""

    def test_courbe24_methode_source_sont_obligatoires(self):
        self.assertEqual(
            sorted(SCHEMA['$defs']['consumption']['required']),
            sorted(['courbe24', 'methode', 'source']))

    def test_saisons_et_appareils_sont_optionnels(self):
        requis = SCHEMA['$defs']['consumption']['required']
        self.assertNotIn('saisons', requis)
        self.assertNotIn('appareils', requis)

    def test_un_document_sans_saisons_ni_appareils_est_valide(self):
        document = copy.deepcopy(SCHEMA['exemple'])
        document['consumption'] = {
            'courbe24': [0.0] * 24,
            'methode': 'facture',
            'source': {'origine': 'atelier', 'saisi_le': '2026-09-23T10:00:00Z'},
        }
        self.assertEqual(erreurs(document), [])

    def test_une_courbe_de_23_valeurs_est_refusee(self):
        document = document_avec_consumption()
        document['consumption']['courbe24'] = document['consumption']['courbe24'][:23]
        constats = erreurs(document)
        self.assertTrue(constats)
        self.assertTrue(any('courbe24' in chemin for chemin, _ in constats))

    def test_une_methode_hors_enumeration_est_refusee(self):
        document = document_avec_consumption()
        document['consumption']['methode'] = 'devinee'
        constats = erreurs(document)
        self.assertTrue(constats)
        self.assertTrue(any('methode' in chemin for chemin, _ in constats))

    def test_un_appareil_sans_kind_est_refuse(self):
        document = document_avec_consumption()
        del document['consumption']['appareils'][0]['kind']
        self.assertTrue(erreurs(document))

    def test_un_billing_hors_enumeration_est_refuse(self):
        document = document_avec_consumption()
        document['consumption']['appareils'][0]['billing'] = 'ailleurs'
        self.assertTrue(erreurs(document))

    def test_les_trois_methodes_du_vocabulaire_sont_acceptees(self):
        for methode in ('facture', 'courbe', 'appareils'):
            document = document_avec_consumption()
            document['consumption']['methode'] = methode
            message = f"methode={methode!r} doit être acceptée"
            self.assertEqual(erreurs(document), [], message)


if __name__ == '__main__':
    unittest.main()
