"""AMOT21 (C-AMOT-019) — le libellé d'option du SERVEUR (``libelle_avec``)
est imprimé partout : un devis BAT-DIFF (« Hybride, batterie plus tard »)
n'affiche plus « Avec batterie », « Stockage + autonomie nocturne », « Réseau
+ Stockage » ni « option … avec batterie » (legacy et résidentiel) ; un devis
avec batterie réelle est inchangé.

Rendu réel : ``build_quote_data`` puis le moteur legacy (HTML capturé avant
WeasyPrint) et le gabarit résidentiel.

Test-du-test : remettre le littéral ``Option 2 — Avec batterie`` ⇒
``test_legacy_libelle_serveur`` échoue.
"""
from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, _residential_sample_data, make_client, make_company,
    make_devis, make_user,
)

LIBELLE = 'Hybride, batterie plus tard'
INTERDITS = ('Option 2 — Avec batterie', 'Stockage + autonomie nocturne',
             'R&#233;seau + Stockage')


class LibelleAvecTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot21-co', nom='AMOT21')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '14', '1100'),
                ('Onduleur réseau 10kW', '1', '11700'),
                ('Onduleur hybride 5kW', '1', '24000'),
                ('Batterie 5 kWh', '1', '14000'),
            ], reference='DEV-AMOT21-1', etude_params=dict(DEUX_OPTIONS))

    def _html_legacy(self, libelle):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        data = build_quote_data(self.devis, clean_pdf_options(
            {'include_etude': True, 'devis_final': True,
             'include_calepinage': False}))
        data['libelle_avec'] = libelle
        capture = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_amot21_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return capture.get('html', '')

    def test_legacy_libelle_serveur(self):
        html = self._html_legacy(LIBELLE)
        self.assertTrue(html)
        for interdit in INTERDITS:
            self.assertNotIn(interdit, html)
        self.assertIn(LIBELLE, html)

    def test_legacy_batterie_reelle_inchangee(self):
        html = self._html_legacy('Avec batterie')
        self.assertIn('Avec batterie', html)


class LibelleAvecResidentielTests(SimpleTestCase):
    def test_residentiel_libelle_serveur(self):
        data = _residential_sample_data()
        data['libelle_avec'] = LIBELLE
        html = render.build_html(renderer._augment(data))
        self.assertNotIn("l'option recommandée — avec batterie", html)
        self.assertNotIn('option avec batterie', html)
