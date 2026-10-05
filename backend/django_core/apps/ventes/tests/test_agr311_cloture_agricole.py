"""AGR311 — clôture de la page 3 agricole alignée sur le canon v6 : « Bon pour
accord », options du kit à cocher avec leur supplément TTC, date butoir
ABSOLUE, QR « Scannez pour signer » seulement avec un lien tokenisé,
échéancier — et AUCUNE annexe de rétractation 31-08 (achat d'exploitation).

HTML réel (``pages.build_html``) + PDF réel (``@tag('pdf')``) : toujours 3
pages avec 8 options.
"""
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.quote_engine.builder import repartition_paiement
from apps.ventes.tests.test_agr310_renderer_agricole import (
    data_complete, fitz, pages_et_debordements,
)

LIEN_TOKENISE = 'https://soleil-agri.example/proposition/ali-fellah/tok-311'


def _data(**kw):
    d = data_complete(**kw)
    d['montants_tranches'] = {
        'sans': repartition_paiement(d['totaux_all']['ttc'],
                                     d['payment_terms'])}
    return d


def _p3(d):
    html = pages.build_html(renderer._augment(d))
    return html.split('<div class="page">')[3]


class Agr311ClotureTests(SimpleTestCase):

    def test_bon_pour_accord_et_date_absolue(self):
        p3 = _p3(_data())
        self.assertIn('Bon pour accord', p3)
        self.assertIn("Offre valable jusqu'au <b>04/11/2026</b>", p3)
        self.assertIn('Pour Soleil Agri', p3)

    def test_chaque_option_avec_son_supplement_ttc(self):
        d = _data(nb_options=3)
        p3 = _p3(d)
        for o in d['options_proposees']:
            with self.subTest(option=o['designation']):
                self.assertIn(f"{o['designation']} <b>+ 950,00 MAD TTC</b>",
                              p3)
        self.assertEqual(p3.count('class="ag-case"'), 3)

    def test_qr_seulement_avec_un_lien_tokenise(self):
        d = _data()
        self.assertNotIn('Scannez pour signer', _p3(d))
        d['links'] = {'signer': 'https://soleil-agri.example/signer/DEV-1'}
        self.assertNotIn('Scannez pour signer', _p3(d))
        d['links'] = {'signer': LIEN_TOKENISE}
        p3 = _p3(d)
        self.assertIn('Scannez pour signer', p3)
        self.assertIn('data:image/png;base64,', p3)

    def test_echeancier_agricole_au_centime(self):
        d = _data()
        m = d['montants_tranches']['sans']
        p3 = _p3(d)
        self.assertIn('30 %', p3)
        self.assertIn('60 %', p3)
        self.assertIn('10 %', p3)
        from apps.ventes.quote_engine.montants import fmt_centimes
        self.assertIn(f"{fmt_centimes(m['acompte'])} MAD", p3)

    def test_signe_au_domicile_ne_joint_pas_l_annexe_31_08(self):
        d = _data()
        d['signe_au_domicile'] = True
        html = pages.build_html(renderer._augment(d))
        self.assertEqual(html.count('<div class="page">'), 3)
        for mot in ('31-08', 'rétractation', 'Rétractation'):
            self.assertNotIn(mot, html)

    def test_aucun_statut_ni_none(self):
        html = pages.build_html(renderer._augment(_data(nb_options=8)))
        self.assertNotIn('None', html)


@tag('pdf')
class Agr311PdfReelTests(SimpleTestCase):

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def test_trois_pages_avec_huit_options_et_qr(self):
        d = _data(nb_lignes_extra=8, nb_options=8)
        d['links'] = {'signer': LIEN_TOKENISE}
        n, debords = pages_et_debordements(renderer.render_pdf_bytes(d))
        self.assertEqual(n, 3)
        self.assertEqual(debords, [])
