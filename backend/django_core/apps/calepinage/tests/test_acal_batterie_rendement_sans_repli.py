"""ACAL306 — batterie à fiche muette sur le rendement aller-retour : plus
aucune valeur de repli (0,90), bloc omis avec motif nommé.

Constat C-ACAL-063 (audit 2026-10-04) : ``specs_batterie`` posait
``rendement_ar_pct = _BATTERY_DEFAULT_ROUND_TRIP`` (0,90, source
« hypothese ») quand la fiche ne le publiait pas — la simulation (batterie
ET hors réseau) chiffrait donc une batterie sur un rendement inventé.

Tenu sur le code réel (``specs_batterie``, l'étape ``etapes/batterie``),
avec des doubles de PRODUIT qui portent une ``fiche_technique`` — la source
lue par ``apps.stock.selectors.specs_for_produit`` (aucune base).

Run :
    python manage.py test apps.calepinage.tests.test_acal_batterie_rendement_sans_repli -v2
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.batterie import specs_batterie
from apps.calepinage.services.etapes import batterie as etape

from .test_conso_batterie_fiche import FICHE_COMPLETE, FausseFiche


class Produit:
    def __init__(self, designation, **champs):
        self.designation = designation
        self.fiche_technique = FausseFiche('batterie', **champs)


def _declaration(specs):
    return {'strategie': 'autoconsommation',
            'groupes': [{'groupe': 'Pack A', 'packs': 1, 'specs': specs}]}


class RendementSansRepliTest(unittest.TestCase):
    def test_fiche_muette_omet_le_bloc_avec_motif(self):
        fiche = dict(FICHE_COMPLETE)
        fiche.pop('bat_rendement_ar_pct')
        specs = specs_batterie(Produit('Pylontech US5000', **fiche))
        rendement = specs['grandeurs']['rendement_ar_pct']
        self.assertIsNone(rendement['valeur'])
        self.assertEqual(
            rendement['mention'],
            'Rendement aller-retour absent de la fiche « Pylontech US5000 » '
            ': complétez la fiche.')
        self.assertIn(rendement['mention'], specs['avertissements'])

        groupes = etape._groupes_declares(_declaration(specs))
        self.assertIsNone(groupes[0]['rendement_ar_pct'])
        self.assertEqual(groupes[0]['motif_rendement'], rendement['mention'])
        # Aucune moyenne ni repli à la place : la banque n'a pas de rendement.
        self.assertIsNone(etape._banque(groupes)['rendement_ar_pct'])

    def test_fiche_complete_appliquee(self):
        specs = specs_batterie(Produit('Pack complet', **FICHE_COMPLETE))
        self.assertEqual(specs['grandeurs']['rendement_ar_pct'],
                         {'valeur': 94.0, 'source': 'fiche',
                          'mention': 'Lu sur la fiche produit.'})
        groupes = etape._groupes_declares(_declaration(specs))
        self.assertEqual(groupes[0]['rendement_ar_pct'], 94.0)

    def test_saisie_appliquee(self):
        """Une valeur SAISIE (CALX404) reste appliquée avec sa source."""
        from apps.calepinage.services.batterie import _rendement

        self.assertEqual(_rendement(92.5), (92.5, 'saisie'))
        self.assertEqual(_rendement({'valeur': 94.0, 'source': 'fiche'}),
                         (94.0, 'fiche'))
