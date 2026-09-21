"""CALX255 — le profil de consommation lu depuis le DOCUMENT (atelier).

Ce qui est tenu :

* un document portant la clé ``consumption`` (CALX251) rend ses 24 valeurs
  horaires et la ``methode`` reprise telle quelle ;
* un document SANS ``consumption`` rend un profil VIDE (``courbe24: None``)
  avec un avertissement — jamais un repli inventé ;
* une courbe qui ne compte pas 24 valeurs est REFUSÉE en nommant le champ.

NOTE — fixture CALX251 : au moment de cette tâche, CALX251 (le contrat
``roof_layout`` v2 déclarant la clé racine ``consumption``) n'est pas encore
construit (aucun fichier
``apps/calepinage/tests/test_calx251_contrat_consommation.py`` sur cette
branche). Ce test construit donc un document ATELIER minimal, CLAIREMENT
SYNTHÉTIQUE, portant la forme attendue par CALX251
(``consumption.courbe24``/``methode``) plutôt que de dépendre d'une fixture
qui n'existe pas encore.

Test PUR : aucune base, aucun réseau.
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.consommation import (
    ProfilInvalide, profil_depuis_layout,
)

# Document ATELIER minimal et SYNTHÉTIQUE (tient lieu de fixture CALX251) —
# 24 valeurs horaires kWh/h choisies arbitrairement pour le test, jamais
# présentées comme une consommation réelle.
DOCUMENT_LAYOUT_CALX251 = {
    'consumption': {
        'courbe24': [float(heure) for heure in range(24)],
        'methode': 'courbe',
        'saisons': {'ete': None, 'hiver': None},
        'appareils': [],
        'source': {'origine': 'atelier', 'saisi_le': None},
    },
}


class ProfilDepuisLayoutTest(unittest.TestCase):

    def test_document_avec_consumption_rend_24_valeurs_et_la_methode(self):
        profil = profil_depuis_layout(DOCUMENT_LAYOUT_CALX251)
        self.assertEqual(len(profil['courbe24']), 24)
        self.assertEqual(profil['courbe24'],
                         [float(heure) for heure in range(24)])
        self.assertEqual(profil['methode'], 'courbe')
        self.assertEqual(profil['source'], 'layout')
        self.assertEqual(profil['pas_minutes'], 60)
        self.assertEqual(profil['total_kwh'], sum(range(24)))
        self.assertEqual(profil['avertissements'], [])

    def test_document_sans_consumption_rend_courbe24_none_et_avertit(self):
        profil = profil_depuis_layout({})
        self.assertIsNone(profil['courbe24'])
        self.assertTrue(profil['avertissements'])
        self.assertEqual(profil['source'], 'layout')

    def test_document_none_rend_aussi_courbe24_none_et_avertit(self):
        profil = profil_depuis_layout(None)
        self.assertIsNone(profil['courbe24'])
        self.assertTrue(profil['avertissements'])

    def test_consumption_sans_courbe24_rend_courbe24_none_et_avertit(self):
        profil = profil_depuis_layout({'consumption': {'methode': 'facture'}})
        self.assertIsNone(profil['courbe24'])
        self.assertTrue(profil['avertissements'])
        # La méthode déclarée reste publiée même sans courbe.
        self.assertEqual(profil['methode'], 'facture')

    def test_une_courbe_de_23_valeurs_est_refusee_en_nommant_le_champ(self):
        document = {
            'consumption': {
                'courbe24': [1.0] * 23,
                'methode': 'courbe',
            },
        }
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_layout(document)
        self.assertEqual(refus.exception.champ, 'consumption.courbe24')

    def test_une_courbe_de_25_valeurs_est_aussi_refusee(self):
        document = {
            'consumption': {
                'courbe24': [1.0] * 25,
                'methode': 'courbe',
            },
        }
        with self.assertRaises(ProfilInvalide) as refus:
            profil_depuis_layout(document)
        self.assertEqual(refus.exception.champ, 'consumption.courbe24')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
