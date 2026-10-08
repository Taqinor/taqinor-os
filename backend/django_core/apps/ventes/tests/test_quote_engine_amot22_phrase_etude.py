"""AMOT22 (C-AMOT-020) — la phrase de méthode de la page « Étude » est
composée depuis le devis (ville de calcul, phases des onduleurs vendus,
« sans batterie » seulement sans batterie) ; plus de « irradiation moyenne du
Maroc » ni de « sans batterie, onduleur réseau, raccordement triphasé » fixes.

Rendu legacy réel (``build_quote_data`` → HTML capturé avant WeasyPrint).

Test-du-test : remettre la phrase fixe ⇒ ``test_mono_avec_batterie`` échoue.
"""
from django.test import TestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

FIXE = "irradiation moyenne du Maroc"

#: Les entrées d'étude (même forme que ``TestEtudeFooter`` du résidentiel) :
#: sans elles la page « Étude » n'est pas rendue.
ETUDE = {
    'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
    'taux_autoconso': 100, 'taux_couverture': 10.4,
    'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
    'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
}


class PhraseEtudeTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot22-co', nom='AMOT22')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _html(self, lignes, etude_params, ville=None):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        self.n += 1
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference='DEV-AMOT22-%d' % self.n,
                           etude_params={**ETUDE, **etude_params})
        devis.mode_installation = 'industriel'
        devis.save(update_fields=['mode_installation'])
        data = build_quote_data(devis, clean_pdf_options(
            {'include_etude': True, 'include_calepinage': False}))
        data['client_ville_libelle'] = ville or ''
        data['client_city'] = ville or ''
        capture = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_amot22_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        html = capture.get('html', '')
        self.assertIn("\u00c9tude d'autoconsommation", html)
        return html

    def test_mono_avec_batterie(self):
        html = self._html([
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau 5kW Monophasé', '1', '9000'),
            ('Onduleur hybride 5kW Monophasé', '1', '15000'),
            ('Batterie 5 kWh', '1', '14000'),
        ], dict(DEUX_OPTIONS), ville='Marrakech')
        self.assertNotIn(FIXE, html)
        self.assertNotIn('sans batterie, onduleur réseau', html)
        self.assertIn('productible de Marrakech', html)
        self.assertIn('raccordement monophasé', html)
        self.assertNotIn('raccordement triphasé', html)

    def test_tri_sans_batterie(self):
        html = self._html([
            ('Panneau mono 550W', '20', '1100'),
            ('Onduleur réseau 10kW Triphasé', '1', '14000'),
        ], {'scenario': 'Sans batterie'}, ville='Agadir')
        self.assertIn('raccordement triphasé', html)
        self.assertIn('sans batterie', html)

    def test_sans_ville(self):
        html = self._html([
            ('Panneau mono 550W', '20', '1100'),
            ('Onduleur réseau 10kW', '1', '14000'),
        ], {'scenario': 'Sans batterie'})
        self.assertNotIn(FIXE, html)
        self.assertNotIn('productible de', html)
