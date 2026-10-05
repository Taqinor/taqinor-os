"""AGR314 — document agricole de 3 pages en arabe et en anglais : tous les
libellés STRUCTURELS du renderer passent par le catalogue unique
``quote_engine.i18n_labels`` (clés ``agr_*``), mise en page RTL en arabe.

HTML réel (``pages.build_html``) : en ``ar`` et en ``en``, aucun libellé
français du catalogue agricole ne reste (la liste des clés ``agr_`` est
parcourue) ; ``dir="rtl"`` en arabe ; le français est inchangé. Les DONNÉES
saisies (désignations, nom du client) ne sont jamais traduites : elles sont
retirées du HTML avant la recherche. PDF réel (``@tag('pdf')``) : 3 pages.
"""
import re

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine import i18n_labels as L
from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.tests.test_agr310_renderer_agricole import (
    data_complete, data_minimale, fitz, pages_et_debordements,
)
from apps.ventes.tests.test_agr311_cloture_agricole import LIEN_TOKENISE

_GABARIT = re.compile(r"\{[a-z_]+\}")


def _data(langue, minimale=False):
    d = data_minimale() if minimale else data_complete(nb_options=2)
    d['langue_sortie'] = langue
    d['links'] = {'signer': LIEN_TOKENISE}
    d['client_name'] = 'Ali Fellah'
    d['existante'] = True
    return d


def _html_sans_donnees(d):
    """Le HTML rendu, sans ce qui n'est pas un libellé : la feuille de style
    (polices en base64), les images ``data:`` et les DONNÉES saisies."""
    html = pages.build_html(renderer._augment(d))
    html = re.sub(r'<style>.*?</style>', '', html, flags=re.S)
    html = re.sub(r'data:[^"\')]+', '', html)
    for it in d['all_items'] + d.get('options_proposees', []):
        html = html.replace(it['designation'], '')
    return html.replace(d['client_name'], '')


def _texte_visible(html):
    """Le texte LU par le client : sans balises ni attributs (les ancres
    ``data-figure``/``data-etape`` sont des marqueurs techniques)."""
    return re.sub(r'<[^>]+>', ' ', html)


def _morceaux_francais(cle, autre):
    """Les fragments FRANÇAIS fixes d'un libellé (hors gabarits ``{…}``),
    seulement quand ils diffèrent de la langue ``autre`` et ont du sens."""
    fr = L.LIBELLES[cle]['fr']
    if fr == L.LIBELLES[cle][autre]:
        return []
    return [m.strip() for m in _GABARIT.split(fr)
            if len(m.strip()) >= 4 and m.strip() not in
            L.LIBELLES[cle][autre]]


CLES_AGR = sorted(c for c in L.LIBELLES if c.startswith('agr_'))


class Agr314LanguesTests(SimpleTestCase):

    def _aucun_libelle_francais(self, langue, minimale=False):
        html = _html_sans_donnees(_data(langue, minimale))
        texte = _texte_visible(html)
        for cle in CLES_AGR:
            for morceau in _morceaux_francais(cle, langue):
                with self.subTest(langue=langue, cle=cle, morceau=morceau):
                    self.assertNotIn(morceau, texte)
        return html

    def test_arabe_rtl_sans_libelle_francais(self):
        html = self._aucun_libelle_francais('ar')
        self.assertIn('<html lang="ar" dir="rtl">', html)
        self.assertIn(L.libelle('agr_titre_p1', 'ar'), html)
        self.assertIn(L.libelle('agr_votre_argent', 'ar'), html)
        self.assertIn(L.libelle('agr_bpa_client', 'ar'), html)
        complet = pages.build_html(renderer._augment(_data('ar')))
        self.assertIn("font-family:'Noto Sans Arabic'", complet)

    def test_arabe_fixture_minimale(self):
        html = self._aucun_libelle_francais('ar', minimale=True)
        self.assertIn(L.libelle('agr_besoin_omis', 'ar'), html)

    def test_anglais_sans_libelle_francais(self):
        html = self._aucun_libelle_francais('en')
        self.assertIn('<html lang="en" dir="ltr">', html)
        self.assertIn('How it works', html)
        self.assertIn('Equipment, price and warranties', html)
        self.assertIn('Pump manufacturer warranty: 3 years', html)

    def test_francais_inchange(self):
        html = pages.build_html(renderer._augment(_data('fr')))
        self.assertTrue(html.startswith("<!doctype html><html><head>"))
        for attendu in ("L'eau de votre exploitation, pompée par le soleil",
                        'Votre argent', 'Comment ça marche',
                        'Équipement, prix et garanties',
                        'Garantie constructeur de la pompe : 3 ans',
                        'Bon pour accord — le client'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, html)

    def test_chaque_cle_agr_porte_les_trois_langues(self):
        for cle in CLES_AGR:
            for langue in L.LANGUES:
                with self.subTest(cle=cle, langue=langue):
                    self.assertTrue(L.LIBELLES[cle][langue].strip())
                    # Mêmes gabarits dans chaque langue.
                    self.assertEqual(
                        sorted(_GABARIT.findall(L.LIBELLES[cle][langue])),
                        sorted(_GABARIT.findall(L.LIBELLES[cle]['fr'])))


@tag('pdf')
class Agr314PdfReelTests(SimpleTestCase):

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def test_trois_pages_en_arabe_et_en_anglais(self):
        for langue in ('ar', 'en', 'fr'):
            with self.subTest(langue=langue):
                n, debords = pages_et_debordements(
                    renderer.render_pdf_bytes(_data(langue)))
                self.assertEqual(n, 3)
                self.assertEqual(debords, [])
