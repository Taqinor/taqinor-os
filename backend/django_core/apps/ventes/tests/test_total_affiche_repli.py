# -*- coding: utf-8 -*-
"""PVAB — le repli d'affichage de la liste ne montre JAMAIS la somme des options.

Incident fondateur (20/08/2026, DEV-202608-0015) : quand ``build_quote_data``
lève, ``display_totals`` retombait sur ``devis.total_ttc`` — pour un devis à
deux options c'est la SOMME des deux paniers (77 584 MAD), un montant qui
n'existe dans AUCUN document — et son ``nb_options: 1`` masquait même le badge
« 2 options ». Ces tests épinglent le repli léger : mêmes prédicats de
classification, même chaîne canonique de la monnaie, sans le moteur PDF.
"""
from unittest.mock import patch

from django.test import TestCase

from apps.ventes.serializers import DevisSerializer
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

_LIGNES_DEUX_OPTIONS = [
    ('Panneau Canadien Solar 710W', '14', '1272.73', '10'),
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', '20'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', '20'),
    ('Batterie Dyness 10 kWh', '1', '25000', '20'),
    ('Installation', '1', '4000', '20'),
]

_MOTEUR = 'apps.ventes.quote_engine.builder.build_quote_data'


class TotalAfficheRepliTests(TestCase):
    """``display_totals`` sous moteur en échec (build_quote_data lève)."""

    @classmethod
    def setUpTestData(cls):
        cls.company = make_company()
        cls.user = make_user(cls.company)
        cls.client_obj = make_client(cls.company)

    def _devis_deux_options(self, reference='DEV-REPLI-2OPT'):
        return make_devis(
            self.company, self.user, self.client_obj, _LIGNES_DEUX_OPTIONS,
            remise_globale='5', reference=reference,
            etude_params=DEUX_OPTIONS)

    def test_moteur_en_echec_jamais_la_somme_des_deux_options(self):
        from apps.ventes.quote_engine.builder import display_totals
        devis = self._devis_deux_options()
        with patch(_MOTEUR, side_effect=RuntimeError('moteur cassé')):
            dt = display_totals(devis)
        self.assertEqual(dt['nb_options'], 2)
        # Jamais la somme mensongère : l'incident affichait total_ttc.
        self.assertLess(dt['total'], float(devis.total_ttc))
        comparaison = dt['comparaison_repli']
        self.assertEqual(dt['total'], float(comparaison['sans']['ttc']))
        # L'option avec batterie coûte plus cher que sans — sinon le split
        # des prédicats est cassé.
        self.assertLess(comparaison['sans']['ttc'], comparaison['avec']['ttc'])
        # La remise globale de 5 % est honorée dans les deux paniers.
        self.assertGreater(comparaison['sans']['remise'], 0)
        self.assertGreater(comparaison['avec']['remise'], 0)

    def test_moteur_en_echec_mono_option_comportement_historique(self):
        from apps.ventes.quote_engine.builder import display_totals
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Pompe immergée 5.5 CV', '1', '9166.67', '20'),
            ('Installation', '1', '4000', '20'),
        ], reference='DEV-REPLI-MONO')
        with patch(_MOTEUR, side_effect=RuntimeError('moteur cassé')):
            dt = display_totals(devis)
        self.assertEqual(dt, {'total': float(devis.total_ttc),
                              'nb_options': 1})

    def test_artefact_non_declare_reste_au_total_stocke(self):
        """PV86 — deux onduleurs SANS déclaration = un seul document dont le
        total EST la somme des lignes : le repli suit la même règle."""
        from apps.ventes.quote_engine.builder import display_totals
        devis = make_devis(
            self.company, self.user, self.client_obj, _LIGNES_DEUX_OPTIONS,
            reference='DEV-REPLI-ARTE', etude_params=None)
        with patch(_MOTEUR, side_effect=RuntimeError('moteur cassé')):
            dt = display_totals(devis)
        self.assertEqual(dt['nb_options'], 1)
        self.assertEqual(dt['total'], float(devis.total_ttc))

    def test_predicat_leger_deux_options_declarees(self):
        from apps.ventes.utils.options import deux_options_declarees
        self.assertTrue(deux_options_declarees(self._devis_deux_options(
            reference='DEV-REPLI-PRED')))
        sans_declaration = make_devis(
            self.company, self.user, self.client_obj, _LIGNES_DEUX_OPTIONS,
            reference='DEV-REPLI-PRE2', etude_params=None)
        self.assertFalse(deux_options_declarees(sans_declaration))
        # Z1 — hybride déclaré mais SANS batterie réelle : jamais deux options.
        hybride_seul = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73', '10'),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', '20'),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', '20'),
        ], reference='DEV-REPLI-PRE3', etude_params=dict(DEUX_OPTIONS))
        self.assertFalse(deux_options_declarees(hybride_seul))

    def test_serializer_expose_les_deux_totaux_sous_moteur_en_echec(self):
        """La liste (DevisSerializer) montre « A / B » même moteur cassé :
        total_affiche = option 1, nb_options = 2, comparaison_options porte
        les deux TTC — et le ROI, qui exige le moteur, reste None partout."""
        devis = self._devis_deux_options(reference='DEV-REPLI-SER')
        ser = DevisSerializer()
        with patch(_MOTEUR, side_effect=RuntimeError('moteur cassé')):
            total_affiche = ser.get_total_affiche(devis)
            nb_options = ser.get_nb_options(devis)
            comparaison = ser.get_comparaison_options(devis)
        self.assertEqual(nb_options, 2)
        self.assertLess(total_affiche, float(devis.total_ttc))
        self.assertEqual(comparaison['nb_options'], 2)
        self.assertEqual(comparaison['sans']['ttc'], total_affiche)
        self.assertLess(comparaison['sans']['ttc'], comparaison['avec']['ttc'])
        self.assertIsInstance(comparaison['sans']['ttc'], float)
        self.assertIsInstance(comparaison['avec']['ttc'], float)
        self.assertTrue(all(v is None for v in comparaison['roi'].values()))
