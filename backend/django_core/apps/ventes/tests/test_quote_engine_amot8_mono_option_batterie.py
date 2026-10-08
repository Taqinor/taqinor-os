"""AMOT8 (C-AMOT-001) — un devis mono-option « onduleur réseau + batterie »
porte TOUTES ses lignes au PDF : la batterie et son prix figurent au tableau
et au total imprimé (= noyau), le scénario stocké « Avec batterie » n'est plus
re-titré « Sans », et le vendeur est averti en interne (« batterie sans
onduleur hybride »).

Rejoue la sonde VA S1/S1b. Décision fondateur 08/10/2026 : un devis envoyé
avant la correction (``regles_calcul = 1``) garde le rendu d'origine.

Test-du-test : retirer ``_reseau_batterie_sans_hybride`` de la condition de
recomposition ⇒ ``test_batterie_presente_et_total_noyau`` échoue.
"""
from decimal import Decimal

from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user)


def _designations(items):
    return [str(it.get('designation') or '') for it in items or []]


class MonoOptionBatterieTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_ = make_client(self.company)

    def _devis(self, lignes, ref, scenario='Avec batterie'):
        return make_devis(
            self.company, self.user, self.client_, lignes, reference=ref,
            etude_params={'scenario': scenario} if scenario else None)

    def _reseau_batterie(self, ref='DEV-AMOT8-0001', scenario='Avec batterie'):
        return self._devis([
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau Huawei 5kW', '1', '8000'),
            ('Batterie Dyness 5kWh', '1', '20000'),
        ], ref, scenario)

    def test_batterie_presente_et_total_noyau(self):
        devis = self._reseau_batterie()
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertTrue(any('Batterie' in d for d in _designations(data['all_items'])))
        self.assertAlmostEqual(float(data['display_total']),
                               float(devis.total_ttc), delta=1.0)
        self.assertAlmostEqual(float(data['totaux_all']['ttc']),
                               float(devis.total_ttc), delta=1.0)
        self.assertTrue(any('batterie sans onduleur hybride' in a
                            for a in data.get('avertissements_internes', [])))

    def test_scenario_stocke_conserve(self):
        data = build_quote_data(self._reseau_batterie(), {'pdf_mode': 'full'})
        self.assertEqual(data['scenario'], 'Avec batterie')

    def test_une_page_imprime_la_batterie(self):
        devis = self._reseau_batterie(ref='DEV-AMOT8-0002', scenario=None)
        data = build_quote_data(devis, {'pdf_mode': 'onepage'})
        self.assertTrue(any('Batterie' in d for d in _designations(data['all_items'])))
        self.assertAlmostEqual(float(data['display_total']),
                               float(devis.total_ttc), delta=1.0)

    def test_regles_d_origine_inchangees(self):
        """Devis envoyé avant la correction : rendu d'hier (batterie absente)."""
        devis = self._reseau_batterie(ref='DEV-AMOT8-0003')
        devis.regles_calcul = 1
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        self.assertFalse(any('Batterie' in d for d in _designations(data['all_items'])))

    def test_temoins_inchanges(self):
        reseau = self._devis([
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau Huawei 5kW', '1', '8000'),
        ], 'DEV-AMOT8-0010', 'Sans batterie')
        data = build_quote_data(reseau, {'pdf_mode': 'full'})
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertFalse(any('batterie sans onduleur hybride' in a
                             for a in data.get('avertissements_internes', [])))
        hybride = self._devis([
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur hybride Deye 5kW', '1', '15000'),
            ('Batterie Dyness 5kWh', '1', '20000'),
        ], 'DEV-AMOT8-0011', 'Avec batterie')
        data = build_quote_data(hybride, {'pdf_mode': 'full'})
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertFalse(any('batterie sans onduleur hybride' in a
                             for a in data.get('avertissements_internes', [])))
        self.assertAlmostEqual(float(data['display_total']),
                               float(hybride.total_ttc), delta=1.0)
        self.assertEqual(Decimal(str(hybride.taux_tva)), Decimal('20.00'))
