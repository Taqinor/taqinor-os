"""AMOT34 (C-AMOT-044) — la légende « palier en année N : provision de
remplacement de l'onduleur, déjà déduite » n'est imprimée que si
``cashflow_assumptions.inverter_replace_cost`` est non nul, avec l'année
servie ``inverter_replace_year``.

Rendu réel du gabarit résidentiel sur les données d'exemple.

Test-du-test : rendre la phrase inconditionnelle ⇒
``test_onduleur_offert_aucune_legende`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import _residential_sample_data

PHRASE = 'provision de remplacement de l&#x27;onduleur'


def _html(cashflow_assumptions):
    data = _residential_sample_data()
    data['cashflow_assumptions'] = cashflow_assumptions
    return render.build_html(renderer._augment(data))


def _a_la_phrase(html):
    return ('provision de remplacement de l\'onduleur, déjà déduite' in html
            or PHRASE in html)


class LegendeProvisionTests(SimpleTestCase):

    def test_onduleur_offert_aucune_legende(self):
        html = _html({'inverter_replace_cost': None,
                      'inverter_replace_year': 12})
        self.assertFalse(_a_la_phrase(html))
        self.assertNotIn('Le palier en année', html)

    def test_onduleur_chiffre_legende_avec_annee(self):
        html = _html({'inverter_replace_cost': 15000,
                      'inverter_replace_year': 11})
        self.assertTrue(_a_la_phrase(html))
        self.assertIn('Le palier en année&nbsp;11', html)


class ProvisionDeuxOptionsTests(SimpleTestCase):
    """RPDF — deux onduleurs de prix différents ⇒ les deux montants."""

    def test_deux_montants_quand_les_onduleurs_different(self):
        html = _html({'inverter_replace_cost': 8000,
                      'inverter_replace_cost_sans': 8000,
                      'inverter_replace_cost_avec': 15000,
                      'inverter_replace_year': 12})
        self.assertIn('(8 000 MAD option 1, 15 000 MAD option 2)', html)

    def test_un_seul_montant_quand_les_onduleurs_sont_egaux(self):
        html = _html({'inverter_replace_cost': 15000,
                      'inverter_replace_cost_sans': 15000,
                      'inverter_replace_cost_avec': 15000,
                      'inverter_replace_year': 12})
        self.assertNotIn('option 1, 15 000 MAD option 2', html)
        self.assertIn('15 000 MAD', html)
