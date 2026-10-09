"""AMOT24 (C-AMOT-023) — tout pourcentage (remise, TVA) s'imprime par UN
formateur à la française (``montants.pct_fr`` : valeur exacte, virgule, sans
zéros inutiles) : une remise de 2,5 % s'imprime « −2,5 % » et
« Remise (2,5 %) » partout ; « 2.5 » et « −2 % » ont disparu ; une remise
entière (2 %) est inchangée.

Rendus réels (legacy 3 pages + une-page, résidentiel premium) depuis
``build_quote_data``. Test-du-test : remettre ``int(DISCOUNT_PCT)`` dans le
badge de remise ⇒ ``test_remise_decimale`` échoue (« −2 % »).
"""
import html as _html
import re

from django.test import SimpleTestCase, TestCase

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.quote_engine.montants import pct_fr
from apps.ventes.quote_engine.residential import render as res_render
from apps.ventes.quote_engine.residential import renderer as res_renderer
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


def _texte(h):
    t = _html.unescape(h)
    return re.sub(r'[   ]', ' ', t)


class PctFrPurTests(SimpleTestCase):
    def test_formateur(self):
        self.assertEqual(pct_fr(2.5), '2,5')
        self.assertEqual(pct_fr('2.50'), '2,5')
        self.assertEqual(pct_fr(2), '2')
        self.assertEqual(pct_fr(20.0), '20')
        self.assertEqual(pct_fr(7.25), '7,25')


class PctFrTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot24-co', nom='AMOT24')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.n = 0

    def _devis(self, remise):
        self.n += 1
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '10', '1100'),
            ('Onduleur réseau Huawei 5kW', '1', '8000'),
            ('Onduleur hybride Deye 5kW', '1', '15000'),
            ('Batterie Dyness 5kWh', '1', '20000'),
        ], remise_globale=remise, reference=f'DEV-AMOT24-{self.n}',
            etude_params=dict(DEUX_OPTIONS))

    def _rendus(self, devis):
        out = []
        with G._RENDER_LOCK:
            for mode in ('full', 'onepage'):
                data = build_quote_data(devis,
                                        clean_pdf_options({'pdf_mode': mode}))
                out.append(_texte(G.render_html_for(
                    {**data, 'pdf_mode': mode})))
        data = build_quote_data(devis, clean_pdf_options({'pdf_mode': 'full'}))
        out.append(_texte(res_render.build_html(
            res_renderer._augment(dict(data)))))
        return out

    def test_remise_decimale(self):
        full, une_page, residentiel = self._rendus(self._devis('2.5'))
        self.assertIn('−2,5 %', full)
        self.assertIn('Remise (2,5 %)', full)
        self.assertIn('2,5 %', une_page)
        for txt in (full, une_page, residentiel):
            self.assertNotIn('2.5 %', txt)
            self.assertNotIn('(2.5', txt)
            self.assertNotIn('−2 %', txt)

    def test_remise_entiere_inchangee(self):
        full, une_page, _res = self._rendus(self._devis('2'))
        self.assertIn('−2 %', full)
        self.assertIn('Remise (2 %)', full)
