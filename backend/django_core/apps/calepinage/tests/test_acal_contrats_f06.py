# -*- coding: utf-8 -*-
"""ACAL56 (moitié back du M0 ACAL9) — les quatre contrats F06 affirmés.

Le M0 ACAL9 a posé SEULS sur ``main`` (PACT10) les quatre échantillons de la
famille électrique ; ACAL56 en est la première consommatrice : elle affirme
qu'ils existent, qu'ils sont complets, et que l'entrée servie par
``GET entree-electrique/`` porte EXACTEMENT les clés promises (celles de
``CHAMPS_ENTREE`` hors ``derogations``, + régime, transformateur, batterie,
hors-réseau). Tests PURS : un calepinage nu (aucune société, aucun devis)
ne touche aucune base.
"""
from __future__ import annotations

import json
import pathlib
import unittest

from apps.calepinage.services.electrique import (
    CHAMPS_ENTREE, CLE_DEROGATIONS, CLES_ENTREE_SERVIE,
    entree_electrique_servie,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parent.parent
                / 'contract_samples')

#: Fichier -> (endpoint EXACT, états d'exemple exigés).
QUATRE = {
    'calepinage_entree_electrique.json': (
        'GET /api/django/calepinage/calepinages/<int:pk>/entree-electrique/',
        ('exemple', 'exemple_vide', 'exemple_refus_400')),
    'calepinage_raccordement.json': (
        'GET /api/django/calepinage/calepinages/<int:pk>/raccordement/',
        ('exemple', 'exemple_vide')),
    'calepinage_modules_disponibles.json': (
        'GET /api/django/calepinage/calepinages/<int:pk>/'
        'modules-disponibles/',
        ('exemple', 'exemple_vide')),
    'calepinage_publication_electrique.json': (
        'POST /api/django/calepinage/calepinages/<int:pk>/generer-devis/',
        ('exemple', 'exemple_refus_422')),
}


def _charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


class _Nu:
    """Un calepinage NU : aucune société, aucun devis — donc aucune base."""

    pk = 1
    company = None
    devis_id = None
    resultat = None
    roof_layout = None


class ContratsF06(unittest.TestCase):

    def test_les_quatre_fichiers_existent_et_sont_complets(self):
        for nom, (endpoint, etats) in QUATRE.items():
            chemin = ECHANTILLONS / nom
            self.assertTrue(chemin.exists(), nom)
            donnees = _charger(nom)
            self.assertEqual(donnees.get('endpoint'), endpoint, nom)
            self.assertTrue(str(donnees.get('pourquoi') or '').strip(), nom)
            for etat in etats:
                self.assertIsInstance(donnees.get(etat), dict,
                                      '%s : « %s » absent' % (nom, etat))

    def test_les_cles_de_l_entree_sont_celles_de_CHAMPS_ENTREE_plus_regime_transformateur_batterie_hors_reseau(self):  # noqa: E501
        attendu = (set(CHAMPS_ENTREE) - {CLE_DEROGATIONS}) | {
            'regime', 'transformateur', 'batterie', 'hors_reseau'}
        self.assertEqual(set(CLES_ENTREE_SERVIE), attendu)
        contrat = _charger('calepinage_entree_electrique.json')
        for etat in ('exemple', 'exemple_vide'):
            self.assertEqual(set(contrat[etat]['entree']), attendu, etat)

    def test_la_forme_servie_est_celle_du_contrat(self):
        contrat = _charger('calepinage_entree_electrique.json')
        servi = entree_electrique_servie(_Nu(), {})
        for etat in ('exemple', 'exemple_vide'):
            self.assertEqual(sorted(servi), sorted(contrat[etat]), etat)
            self.assertEqual(sorted(servi['entree']),
                             sorted(contrat[etat]['entree']), etat)
            self.assertEqual(sorted(servi['materiel']),
                             sorted(contrat[etat]['materiel']), etat)
            self.assertEqual(sorted(servi['candidats']),
                             sorted(contrat[etat]['candidats']), etat)
        # Le calepinage nu : la forme de l'exemple vide, valeur pour valeur.
        self.assertEqual(servi['entree'],
                         contrat['exemple_vide']['entree'])
        self.assertEqual(servi['materiel'],
                         contrat['exemple_vide']['materiel'])
        self.assertEqual(servi['candidats'],
                         contrat['exemple_vide']['candidats'])

    def test_l_entree_est_relue_telle_qu_ecrite(self):
        ecrite = {'module_produit': 4112, 'dc_m': 25.0, 'regime': 'TT',
                  'derogations': [{'code': 'x', 'motif': 'y'}]}
        servi = entree_electrique_servie(_Nu(), ecrite)
        self.assertEqual(servi['entree']['module_produit'], 4112)
        self.assertEqual(servi['entree']['dc_m'], 25.0)
        self.assertEqual(servi['entree']['regime'], 'TT')
        self.assertNotIn('derogations', servi['entree'])
