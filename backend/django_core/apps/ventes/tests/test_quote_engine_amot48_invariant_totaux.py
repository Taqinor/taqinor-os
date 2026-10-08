"""AMOT48 — garde de classe : « Σ lignes imprimées TTC = total imprimé =
totaux du noyau » (``display_total == totaux_all.ttc`` sur un document à une
option) ; écart ⇒ avertissement interne + règle nocturne
``DOC_TOTAL_IMPRIME_NE_NOYAU``.

Test-du-test : remettre ``_all_rows = sans_items`` sans AMOT8 (mono-option
réseau + batterie) ⇒ la garde nomme l'écart (``test_branches_du_builder``).
"""
from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine.builder import (
    build_quote_data, ecarts_totaux_imprimes)
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user)


def _data(affiche, tout, sans=None, avec=None, nb=1, **extra):
    d = {'display_total': affiche, 'nb_options': nb,
         'totaux_all': {'ttc': tout}}
    if sans is not None:
        d['totaux_sans'] = {'ttc': sans}
    if avec is not None:
        d['totaux_avec'] = {'ttc': avec}
    d.update(extra)
    return d


class InvariantTotauxPurTests(SimpleTestCase):
    def test_sain(self):
        self.assertEqual(ecarts_totaux_imprimes(_data(47000, 47000), 47000), [])

    def test_defaut_amot8_nomme(self):
        """VA S1 : display 23 000, lignes imprimées 23 000, noyau 47 000."""
        ecarts = ecarts_totaux_imprimes(_data(23000, 23000), 47000)
        self.assertTrue(any('noyau' in e for e in ecarts))

    def test_defaut_amot10_nomme(self):
        """VA s5b : variante « avec » rendue, display 23 000, totaux_all 53 000."""
        ecarts = ecarts_totaux_imprimes(
            _data(23000, 53000, sans=23000, avec=53000, variante_rendue=True))
        self.assertTrue(any('Σ lignes' in e for e in ecarts))

    def test_deux_options_total_de_l_option(self):
        self.assertEqual(ecarts_totaux_imprimes(
            _data(53000, 76000, sans=23000, avec=53000, nb=2), 53000), [])

    def test_multi_villas(self):
        self.assertEqual(ecarts_totaux_imprimes(
            _data(20000, 20000, display_total_multi=60000), 60000), [])


class InvariantTotauxTests(TestCase):
    """Les branches réelles de ``build_quote_data`` tiennent l'invariant."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def test_branches_du_builder(self):
        cas = [
            ([('Panneau mono 550W', '10', '1100'),
              ('Onduleur réseau Huawei 5kW', '1', '8000'),
              ('Batterie Dyness 5kWh', '1', '20000')],
             {'scenario': 'Avec batterie'}, '0'),
            ([('Panneau mono 550W', '10', '1100'),
              ('Onduleur réseau Huawei 5kW', '1', '8000'),
              ('Onduleur hybride Deye 5kW', '1', '12000'),
              ('Batterie Dyness 5kWh', '1', '15000')],
             dict(DEUX_OPTIONS), '7.5'),
            ([('Panneau mono 550W', '10', '1100.55'),
              ('Onduleur réseau Huawei 5kW', '1', '8000')],
             None, '3.5'),
        ]
        for n, (lignes, params, remise) in enumerate(cas):
            with self.subTest(n=n):
                devis = make_devis(self.company, self.user, self.client_,
                                   lignes, remise_globale=remise,
                                   reference=f'DEV-AMOT48-{n:04d}',
                                   etude_params=params)
                data = build_quote_data(devis, {'pdf_mode': 'full'})
                self.assertEqual(
                    ecarts_totaux_imprimes(data, devis.total_ttc), [])
                self.assertFalse(any(
                    a.startswith('totaux :')
                    for a in data.get('avertissements_internes', [])))
