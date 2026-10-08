"""AMOT38 (C-AMOT-047) — les « Clauses particulières » du PDF industriel sont
imprimées UNE fois (page équipements, comme le commercial) : plus de second
bloc dans ``industriel/trust.py``.

Rendu réel des gabarits industriel et commercial sur leurs données
d'exemple, clause unique injectée.

Test-du-test : remettre ``{clauses_html}`` dans ``industriel/trust.py`` ⇒
``test_industriel_une_fois`` échoue.
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.commercial import render as com_render
from apps.ventes.quote_engine.commercial import renderer as com_renderer
from apps.ventes.quote_engine.commercial import sample_data as com_sample
from apps.ventes.quote_engine.industriel import render as ind_render
from apps.ventes.quote_engine.industriel import renderer as ind_renderer
from apps.ventes.quote_engine.industriel import sample_data as ind_sample

MARQUEUR = 'texte-unique-ABC123'
CLAUSES = [{'nom': 'Clause QA', 'corps_texte': MARQUEUR}]


class ClausesUniqueTests(SimpleTestCase):

    def test_industriel_une_fois(self):
        data = ind_sample.build()
        data['clauses_cgv'] = CLAUSES
        html = ind_render.build_html(ind_renderer._augment(data))
        self.assertEqual(html.count(MARQUEUR), 1)

    def test_commercial_une_fois(self):
        data = com_sample.build()
        data['clauses_cgv'] = CLAUSES
        html = com_render.build_html(com_renderer._augment(data))
        self.assertEqual(html.count(MARQUEUR), 1)
