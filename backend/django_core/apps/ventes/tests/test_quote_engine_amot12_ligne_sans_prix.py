"""AMOT12 (C-AMOT-007) — le moteur suit la tolérance du noyau pour une ligne
produit SANS prix ou SANS quantité : imprimée à 0,00 avec sa désignation,
DITE en avertissement interne, total imprimé = noyau ; plus aucun 500.

Moteur réel (``build_quote_data``), modèle ``LigneDevis`` réel (null=True).

Test-du-test : remettre ``Decimal(ligne.prix_unitaire)`` ⇒ TypeError.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import LigneDevis
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_produit, make_user,
)


class LigneSansPrixTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot12-co', nom='AMOT12')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '12', '1100'),
                ('Onduleur réseau 5kW', '1', '11700'),
            ], reference='DEV-AMOT12-1')

    def _ajouter(self, **champs):
        produit = make_produit(self.company, 'Coffret AC', 'AMOT12-COF', '500')
        return LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Coffret AC',
            remise=Decimal('0'), **champs)

    def _data(self):
        return build_quote_data(self.devis,
                                clean_pdf_options({'pdf_mode': 'onepage'}))

    def _verifier(self, data):
        items = [it for it in data['all_items']
                 if it['designation'] == 'Coffret AC']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['prix_unit_ht'] * items[0]['quantite'], 0)
        self.assertTrue(any('Coffret AC' in a
                            for a in data.get('avertissements_internes', [])))
        self.assertAlmostEqual(float(data['totaux_all']['ttc']),
                               float(self.devis.total_ttc), places=2)

    def test_ligne_sans_prix(self):
        self._ajouter(prix_unitaire=None, quantite=Decimal('1'))
        self._verifier(self._data())

    def test_ligne_sans_quantite(self):
        self._ajouter(prix_unitaire=Decimal('500'), quantite=None)
        self._verifier(self._data())
