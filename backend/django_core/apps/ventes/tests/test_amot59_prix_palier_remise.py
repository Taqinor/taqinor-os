"""AMOT59 (C-AMOT-035) — le curseur batterie de la page client publie le prix
de VENTE d'un palier (coût catalogue × remise du devis, palier ARRONDI-100)
par UNE fonction ``prix_client_composition`` partagée avec l'échelle et les
cartes Éco/Max ; son payback est ``payback_publiable`` (AMOT29) sur ce prix.

Devis réel (remise 10 %), ``facteur_remise_du_devis`` réel, aucun mock.
Test-du-test : remettre ``'cout_ttc': palier.get('cout_ttc')`` brut dans
``_balayage_stockage_publique`` ⇒ ``test_curseur_remise`` échoue (49 322,08).
"""
from django.test import TestCase

from apps.ventes.domain.dimensionnement_devis import (
    facteur_remise_du_devis, prix_client_composition,
)
from apps.ventes.public.payload_batterie import _balayage_stockage_publique
from apps.ventes.quote_engine.pricing import payback_publiable
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


class PrixPalierRemiseTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot59-co', nom='AMOT59')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '10', '1100'),
                ('Onduleur hybride Deye 5kW', '1', '15000'),
                ('Batterie Dyness 5kWh', '1', '20000'),
            ], remise_globale='10', reference='DEV-AMOT59-1')

    def test_fonction_partagee(self):
        self.assertAlmostEqual(facteur_remise_du_devis(self.devis), 0.9,
                               places=6)
        self.assertEqual(prix_client_composition(49322.08, self.devis),
                         44300.0)
        self.assertEqual(prix_client_composition(49322.08, facteur=0.9),
                         44300.0)
        self.assertIsNone(prix_client_composition(None, self.devis))

    def test_curseur_remise(self):
        dimensionnement = {'recommandation_avec': {'balayage_stockage': [{
            'capacite_kwh': 5.0, 'cout_ttc': 49322.08,
            'lignes_batterie': [{'quantite': 1}],
            'payback_annees': 6.32, 'economie_mad': 7936.0,
        }]}}
        palier = _balayage_stockage_publique(
            dimensionnement, self.devis)['paliers'][0]
        self.assertEqual(palier['cout_ttc'], 44300.0)
        self.assertEqual(palier['payback_annees'], payback_publiable(
            44300.0, 7936.0, stockage=True)['payback_years'])

    def test_sans_devis_passe_directe(self):
        dimensionnement = {'recommandation_avec': {'balayage_stockage': [{
            'capacite_kwh': 5.0, 'cout_ttc': 49322.08,
            'lignes_batterie': [{'quantite': 1}],
            'payback_annees': 6.32, 'economie_mad': 7936.0,
        }]}}
        palier = _balayage_stockage_publique(dimensionnement)['paliers'][0]
        self.assertEqual(palier['cout_ttc'], 49322.08)
        self.assertEqual(palier['payback_annees'], 6.32)
