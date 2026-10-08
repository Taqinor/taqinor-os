"""AMOT10 (C-AMOT-005) — le document « option » téléchargé décrit UNE option
et UN total : quand la variante demandée rétrécit le document
(``deux_options=False`` après QF6), ``display_total`` est celui de cette
variante (= ``totaux_all.ttc``), jamais celui de l'option signée.

Rejoue la sonde VA s5b/s5c (commercial, industriel, résidentiel :
``display_total 23000.0`` / ``totaux_all 53000.0``). Sans variante, le total de
l'option signée reste imprimé (QJR401).

Test-du-test : retirer ``and not _variante_retrecie`` du bloc QJR401 ⇒ rouge.
"""
from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user)

LIGNES = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
    ('Onduleur hybride Deye 5kW', '1', '12000'),
    ('Batterie Dyness 5kWh', '1', '15000'),
]


class VarianteSigneeTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def _devis(self, mode, n):
        devis = make_devis(self.company, self.user, self.client_, LIGNES,
                           reference=f'DEV-AMOT10-{n:04d}',
                           etude_params=dict(DEUX_OPTIONS))
        devis.mode_installation = mode
        devis.option_acceptee = 'sans_batterie'
        devis.save(update_fields=['mode_installation', 'option_acceptee'])
        return devis

    def test_trois_marches_variante_avec(self):
        for n, mode in enumerate(('residentiel', 'commercial', 'industriel')):
            with self.subTest(mode=mode):
                devis = self._devis(mode, n)
                data = build_quote_data(devis, {'variante_option': 'avec'})
                self.assertEqual(data['nb_options'], 1)
                self.assertEqual(float(data['display_total']),
                                 float(data['totaux_all']['ttc']))
                self.assertEqual(float(data['display_total']),
                                 float(data['totaux_avec']['ttc']))

    def test_sans_variante_total_option_signee(self):
        devis = self._devis('residentiel', 10)
        data = build_quote_data(devis, {})
        self.assertEqual(float(data['display_total']),
                         float(data['totaux_sans']['ttc']))

    def test_regles_d_origine_inchangees(self):
        devis = self._devis('residentiel', 11)
        devis.regles_calcul = 1
        data = build_quote_data(devis, {'variante_option': 'avec'})
        self.assertEqual(float(data['display_total']),
                         float(data['totaux_sans']['ttc']))
