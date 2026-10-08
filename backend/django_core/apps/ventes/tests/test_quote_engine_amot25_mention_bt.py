"""AMOT25 (C-AMOT-025) — toute surface résidentielle BT imprime la seule
mention sourcée ``constants_82_21.MENTION_BT`` (+ « seuls les kWh
autoconsommés réduisent la facture ») au lieu de « plafond d'injection 20 %
intégré, rachat BT non publié ».

Hypothèses réelles de ``build_quote_data`` et notes de
``pricing.cashflow_assumptions``.

Test-du-test : remettre la chaîne historique dans ``builder.py`` ⇒
``test_hypotheses_build_quote_data`` échoue.
"""
from django.test import TestCase

from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.quote_engine.constants_82_21 import MENTION_BT
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

INTERDITS = ('non publi', "plafond d'injection 20")


class MentionBtTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot25-co', nom='AMOT25')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '14', '1100'),
                ('Onduleur réseau 10kW', '1', '11700'),
                ('Onduleur hybride 5kW', '1', '24000'),
                ('Batterie 5 kWh', '1', '14000'),
            ], reference='DEV-AMOT25-1', etude_params=dict(DEUX_OPTIONS))

    def test_hypotheses_build_quote_data(self):
        data = build_quote_data(self.devis,
                                clean_pdf_options({'include_etude': True}))
        bloc = data.get('hypotheses') or {}
        items = bloc.get('items') if isinstance(bloc, dict) else bloc
        texte = ' '.join(str(h) for h in items or [])
        self.assertIn(MENTION_BT, texte)
        for interdit in INTERDITS:
            self.assertNotIn(interdit, texte)

    def test_notes_cashflow(self):
        from apps.ventes.quote_engine import pricing
        notes = pricing.cashflow_assumptions().get('notes') or []
        texte = ' '.join(notes)
        self.assertIn(MENTION_BT, texte)
        for interdit in INTERDITS:
            self.assertNotIn(interdit, texte)
