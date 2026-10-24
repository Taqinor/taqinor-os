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

    def test_options_du_kit_traduites(self):
        """AGQ11 — les options NOMMÉES du kit (sans ligne chiffrée) et le
        « non inclus » complété sont des libellés structurels traduits."""
        from core.pompage.kit import OPTIONS
        for langue in ('ar', 'en'):
            d = _data(langue)
            d['etude']['kit'] = {'inclus': [], 'options': [
                {'cle': cle, 'libelle': libelle, 'prix_connu': False}
                for cle, _role, libelle in OPTIONS]}
            texte = _texte_visible(_html_sans_donnees(d))
            with self.subTest(langue=langue):
                self.assertIn(L.libelle('agr_option_cable_descente', langue),
                              texte)
                self.assertIn(L.libelle('agr_prix_sur_devis', langue), texte)
                self.assertIn(
                    L.libelle('agr_option_mention_compteur_eau', langue),
                    texte)
                for cle in ('agr_prix_sur_devis', 'agr_option_cable_descente',
                            'agr_option_mention_compteur_eau'):
                    for morceau in _morceaux_francais(cle, langue):
                        self.assertNotIn(morceau, texte)

    def test_chaque_cle_agr_porte_les_trois_langues(self):
        for cle in CLES_AGR:
            for langue in L.LANGUES:
                with self.subTest(cle=cle, langue=langue):
                    self.assertTrue(L.LIBELLES[cle][langue].strip())
                    # Mêmes gabarits dans chaque langue.
                    self.assertEqual(
                        sorted(_GABARIT.findall(L.LIBELLES[cle][langue])),
                        sorted(_GABARIT.findall(L.LIBELLES[cle]['fr'])))


_ARABE = re.compile('[؀-ۿ]')


def _data_agronomique(langue):
    """Besoin AGRONOMIQUE (cultures connues) : la carte hectares s'imprime."""
    d = _data(langue)
    etude = d['etude']
    etude['besoin'] = {'mode': 'fao', 'region': 'souss-massa',
                       'cultures': [{'crop': 'agrumes', 'surface_ha': 5,
                                     'irrigation': 'goutte'}]}
    etude['besoin_mensuel'] = {'m3_jour_mois': [120] * 12,
                               'nature': 'agronomique_plein',
                               'source_et0': 'FAO-56'}
    etude['ha_irrigables'] = {'valeur': 4.4}
    return d


class Arabe(SimpleTestCase):
    """AGQ13 (C-AGQ-012) — l'arabe lisible en page 2 et unités traduites."""

    def test_unites_traduites_et_legendes_hors_svg(self):
        html = pages.build_html(renderer._augment(_data_agronomique('ar')))
        p1, p2 = html.split('<div class="page">')[1:3]
        self.assertIn('10,2 حصان', p1)
        self.assertIn('4,4 هكتار', p1)
        self.assertIn(L.libelle('unite_kwc', 'ar'), p1)
        self.assertNotIn(' CV<', p1)
        self.assertNotIn(' ha<', p1)
        # Aucun texte arabe dans un <text> SVG de la page 2 ...
        for texte in re.findall(r'<text[^>]*>(.*?)</text>', p2, flags=re.S):
            with self.subTest(texte=texte):
                self.assertIsNone(_ARABE.search(texte))
        # ... mais en légendes HTML : boîtes du schéma, axes, mois.
        hors_svg = re.sub(r'<svg.*?</svg>', ' ', p2, flags=re.S)
        for cle in ('agr_schema_pompe', 'agr_schema_forage', 'agr_moisc_1'):
            with self.subTest(cle=cle):
                self.assertIn(L.libelle(cle, 'ar'), hors_svg)
        self.assertIn('position:absolute', hors_svg)

    def test_francais_identique(self):
        d = _data_agronomique('fr')
        aug = renderer._augment(d)
        html = pages.build_html(aug)
        p1, p2 = html.split('<div class="page">')[1:3]
        self.assertIn(aug['synthese']['schema_svg'], p2)
        self.assertNotIn('ag-sch', html)
        self.assertNotIn('position:absolute', p2)
        self.assertIn('10,2 CV', p1)
        self.assertIn('kWc', p1)
        self.assertIn('>Jan</text>', p2)
        self.assertEqual(aug['synthese']['schema_legendes'], [])


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
