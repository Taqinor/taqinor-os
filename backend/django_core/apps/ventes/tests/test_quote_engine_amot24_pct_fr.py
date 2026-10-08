"""AMOT24 (C-AMOT-023) — tout pourcentage (remise, TVA) s'imprime par UN
formateur à la française (``montants.pct_fr`` : valeur exacte, virgule, sans
zéros inutiles) : une remise de 2,5 % s'imprime « −2,5 % » partout.

Rejoue VA p9 (full ``['−2 % REMISE', …]``, ``['Remise (2.5 %)', …]``,
``['Remise de 2.5 %']`` ; une-page ``['Remise (2.5 %)']``). Une remise entière
(2 %) est inchangée ; un devis aux règles d'origine garde ses formats.

Test-du-test : remettre ``int(DISCOUNT_PCT)`` dans le badge ⇒ rouge.
"""
from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.montants import pct_fr
from apps.ventes.quote_engine.residential import render, renderer
from apps.ventes.tests._quote_engine_common import _residential_sample_data


def _n(txt):
    """Espaces insécables (fine ou non) ramenées à l'espace simple."""
    return (txt.replace('\u202f', ' ').replace('\xa0', ' ')
            .replace('&#8201;', ' '))


class PctFrTests(SimpleTestCase):
    def test_formateur(self):
        self.assertEqual(pct_fr(2.5), '2,5')
        self.assertEqual(pct_fr(2), '2')
        self.assertEqual(pct_fr(20.0), '20')
        self.assertEqual(pct_fr('12.25'), '12,25')
        self.assertEqual(pct_fr(3.50), '3,5')

    def _avec_globals(self, discount, corrige, fn):
        sauve = (G.DISCOUNT_PCT, G.REGLES_CORRIGEES)
        G.DISCOUNT_PCT, G.REGLES_CORRIGEES = discount, corrige
        try:
            return fn()
        finally:
            G.DISCOUNT_PCT, G.REGLES_CORRIGEES = sauve

    def test_legacy_note_remise(self):
        txt = _n(self._avec_globals(2.5, True, G._note_remise_par_ligne))
        self.assertIn('Remise de 2,5 %', txt)
        self.assertNotIn('2.5', txt)
        txt = _n(self._avec_globals(2.0, True, G._note_remise_par_ligne))
        self.assertIn('Remise de 2 %', txt)

    def test_legacy_regles_d_origine(self):
        txt = _n(self._avec_globals(2.5, False, G._note_remise_par_ligne))
        self.assertIn('Remise de 2.5 %', txt)

    def test_legacy_tva(self):
        self._avec_globals(0, True, lambda: self.assertEqual(
            G._pct_txt(20.0), '20'))
        self._avec_globals(0, True, lambda: self.assertEqual(
            G._pct_txt(5.5), '5,5'))

    def test_residentiel_note_remise(self):
        data = _residential_sample_data()
        data['discount_pct'] = 2.5
        html = _n(render.build_html(renderer._augment(data)))
        self.assertIn('Remise de 2,5 %', html)
        self.assertNotIn('Remise de 2.5 %', html)


class PctFrRenduLegacyTests(TestCase):
    """Rendu legacy réel (HTML capturé avant WeasyPrint) d'un devis remisé."""

    def test_full_et_une_page(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        from apps.ventes.tests._quote_engine_common import (
            DEUX_OPTIONS, make_client, make_company, make_devis, make_user)
        company = make_company()
        devis = make_devis(company, make_user(company), make_client(company), [
            ('Panneau mono 550W', '14', '1100'),
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
        ], remise_globale='2.5', reference='DEV-AMOT24-1',
            etude_params=dict(DEUX_OPTIONS))
        for mode in ('full', 'onepage'):
            data = build_quote_data(devis, clean_pdf_options(
                {'pdf_mode': mode, 'include_calepinage': False}))
            capture = {}
            orig = G._render_pdf_weasyprint
            G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
            try:
                G.generate_premium_pdf(data, '/tmp/_amot24_test.pdf')
            finally:
                G._render_pdf_weasyprint = orig
            html = capture.get('html', '')
            self.assertIn('2,5', html, mode)
            self.assertNotIn('Remise (2.5', html, mode)
            self.assertNotIn('−2 %', html, mode)
