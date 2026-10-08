"""AMOT11 (C-AMOT-006) — un devis à ``taux_tva = 0`` dont les lignes n'ont pas
de taux propre : le moteur respecte 0 % (``is not None``, même règle que
``LigneDevis.taux_tva_effectif``) ⇒ TTC du PDF = TTC du noyau.

Rejoue la sonde VA S6/b16 (noyau 62 300,00, moteur 74 800,0).

Test-du-test : remettre ``devis.taux_tva or Decimal(20)`` ⇒ rouge.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)

LIGNES = [('Panneau mono 550W', '10', '1100'),
          ('Onduleur réseau Huawei 5kW', '1', '8000')]


class TvaZeroTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def _devis(self, ref, taux):
        devis = make_devis(self.company, self.user, self.client_, LIGNES,
                           reference=ref)
        devis.taux_tva = taux
        devis.save(update_fields=['taux_tva'])
        return devis

    def test_tva_zero_ttc_egal_noyau(self):
        devis = self._devis('DEV-AMOT11-0001', Decimal('0'))
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertAlmostEqual(float(data['totaux_all']['ttc']),
                               float(devis.total_ttc), delta=0.01)
        self.assertEqual(float(data['taux_tva']), 0.0)
        self.assertAlmostEqual(float(data['totaux_all']['ttc_avant']),
                               float(data['totaux_all']['ht_brut']), delta=100)

    def test_tva_vingt_inchangee(self):
        devis = self._devis('DEV-AMOT11-0002', Decimal('20'))
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertAlmostEqual(float(data['totaux_all']['ttc']),
                               float(devis.total_ttc), delta=0.01)

    def test_regles_d_origine_inchangees(self):
        devis = self._devis('DEV-AMOT11-0003', Decimal('0'))
        devis.regles_calcul = 1
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertEqual(float(data['taux_tva']), 20.0)
