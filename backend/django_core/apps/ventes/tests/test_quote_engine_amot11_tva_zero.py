"""AMOT11 (C-AMOT-006) — un taux de TVA de devis à 0 % est respecté par le
moteur (``is not None``, même règle que ``LigneDevis.taux_tva_effectif``) :
TTC imprimé = TTC du noyau ; ``ttc_avant`` suit la même règle.

Moteur réel, noyau réel (``Devis.total_ttc``). Test-du-test : remettre
``devis.taux_tva or Decimal(20)`` ⇒ ``test_tva_zero_ttc_noyau`` échoue.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

_LIGNES = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
]


class TvaZeroTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot11-co', nom='AMOT11')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, taux, ref):
        devis = make_devis(self.company, self.user, self.client_obj, _LIGNES,
                           reference=ref)
        Devis.objects.filter(pk=devis.pk).update(taux_tva=Decimal(taux))
        devis.refresh_from_db()
        return devis

    def test_tva_zero_ttc_noyau(self):
        devis = self._devis('0', 'DEV-AMOT11-0')
        for mode in ('full', 'onepage'):
            data = build_quote_data(devis,
                                    clean_pdf_options({'pdf_mode': mode}))
            self.assertAlmostEqual(float(data['totaux_all']['ttc']),
                                   float(devis.total_ttc), places=2)
            self.assertAlmostEqual(float(data['totaux_all']['tva']), 0.0,
                                   places=2)
            self.assertAlmostEqual(float(data['totaux_all']['ttc_avant']),
                                   float(data['totaux_all']['ht_brut']),
                                   delta=100)
            self.assertAlmostEqual(float(data['display_total']),
                                   float(devis.total_ttc), places=2)

    def test_taux_vingt_inchange(self):
        devis = self._devis('20', 'DEV-AMOT11-20')
        data = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))
        self.assertAlmostEqual(float(data['totaux_all']['ttc']),
                               float(devis.total_ttc), places=2)
        self.assertGreater(float(data['totaux_all']['tva']), 0)
