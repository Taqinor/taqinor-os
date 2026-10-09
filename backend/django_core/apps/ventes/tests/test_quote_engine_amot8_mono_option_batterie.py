"""AMOT8 (C-AMOT-001) — un devis mono-option « onduleur RÉSEAU + batterie »
(sans onduleur hybride) imprime TOUTES ses lignes : la batterie figure au
tableau et au total imprimé (= ``Devis.total_ttc`` du noyau), le scénario
stocké « Avec batterie » n'est plus re-titré « Sans », et un avertissement
interne nomme « batterie sans onduleur hybride ».

Moteur réel (``build_quote_data``), noyau réel (``Devis.total_ttc``), aucun
mock. Test-du-test : retirer la recomposition AMOT8 de ``builder`` (retour à
``_all_rows = sans_items``) ⇒ ``test_batterie_presente_et_total_noyau`` échoue.
"""
from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

_RESEAU_BATTERIE = [
    ('Panneau mono 550W', '10', '1100'),
    ('Onduleur réseau Huawei 5kW', '1', '8000'),
    ('Batterie Dyness 5kWh', '1', '20000'),
]


class MonoOptionBatterieTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot8-co', nom='AMOT8')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, lignes, ref, etude_params=None):
        return make_devis(self.company, self.user, self.client_obj, lignes,
                          reference=ref, etude_params=etude_params)

    def _data(self, devis, mode='full'):
        return build_quote_data(devis, clean_pdf_options({'pdf_mode': mode}))

    @staticmethod
    def _designations(rows):
        return [it['designation'] for it in rows]

    def test_batterie_presente_et_total_noyau(self):
        devis = self._devis(_RESEAU_BATTERIE, 'DEV-AMOT8-1')
        for mode in ('full', 'onepage'):
            data = self._data(devis, mode)
            self.assertIn('Batterie Dyness 5kWh',
                          self._designations(data['all_items']), mode)
            self.assertAlmostEqual(float(data['display_total']),
                                   float(devis.total_ttc), places=2)
            self.assertAlmostEqual(float(data['totaux_all']['ttc']),
                                   float(devis.total_ttc), places=2)
            self.assertTrue(any(
                'batterie sans onduleur hybride' in a
                for a in data.get('avertissements_internes', [])))
        # CLAUSE PERSISTANCE — rouvrir et re-rendre : identique, aucune écriture.
        avant = devis.etude_params
        d1 = self._data(devis)
        devis.refresh_from_db()
        d2 = self._data(devis)
        self.assertEqual(devis.etude_params, avant)
        self.assertEqual(d1['display_total'], d2['display_total'])
        self.assertEqual(self._designations(d1['all_items']),
                         self._designations(d2['all_items']))

    def test_scenario_stocke_conserve(self):
        devis = self._devis(_RESEAU_BATTERIE, 'DEV-AMOT8-2',
                            etude_params={'scenario': 'Avec batterie'})
        data = self._data(devis)
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertIn('Batterie Dyness 5kWh',
                      self._designations(data['all_items']))
        self.assertAlmostEqual(float(data['display_total']),
                               float(devis.total_ttc), places=2)

    def test_temoins_inchanges(self):
        reseau = self._devis([
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau Huawei 5kW', '1', '8000'),
        ], 'DEV-AMOT8-3')
        data = self._data(reseau)
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertAlmostEqual(float(data['display_total']),
                               float(reseau.total_ttc), places=2)
        self.assertFalse(any(
            'batterie sans onduleur hybride' in a
            for a in data.get('avertissements_internes', [])))

        hybride = self._devis([
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur hybride Deye 5kW', '1', '15000'),
            ('Batterie Dyness 5kWh', '1', '20000'),
        ], 'DEV-AMOT8-4')
        data = self._data(hybride)
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertIn('Batterie Dyness 5kWh',
                      self._designations(data['all_items']))
        self.assertAlmostEqual(float(data['display_total']),
                               float(hybride.total_ttc), places=2)
        self.assertFalse(any(
            'batterie sans onduleur hybride' in a
            for a in data.get('avertissements_internes', [])))
