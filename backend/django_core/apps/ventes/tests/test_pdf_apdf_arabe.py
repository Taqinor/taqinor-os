"""APDF6 (C-APDF-002) — les documents ARABES n'embarquent plus d'@font-face
woff2 « Noto Sans Arabic » vendorisé (homonyme de la police système de
l'image : glyphes superposés mesurés) ; une seule CSS arabe partagée
(``premium_base.css_arabe``) : police système, letter-spacing 0.

Rendu réel des trois moteurs (résidentiel, agricole, une-page / legacy) ;
aucune doublure du moteur.

Test-du-test : réintroduire ``_font_face("Noto Sans Arabic", 400, ...)``
dans ``_css_arabe`` ⇒ ``test_aucun_font_face_homonyme`` échoue.

APDF11 — le devis résidentiel premium arabe est une page RTL
(``ResidentielRtlTests``), toujours 3 pages ; fr et en inchangés.
"""
import re

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine import premium_base
from apps.ventes.quote_engine.agricole import pages as agr_pages
from apps.ventes.quote_engine.agricole import renderer as agr_renderer
from apps.ventes.quote_engine.residential import theme
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete

FONT_FACE_ARABE = re.compile(
    r"@font-face\s*\{[^}]*Noto Sans Arabic", re.IGNORECASE)


def _data_agricole_ar():
    from apps.ventes.quote_engine import i18n_labels
    d = data_complete()
    d['langue_sortie'] = 'ar'
    d['libelles_document'] = i18n_labels.libelles('ar')
    return agr_renderer._augment(d)


class PoliceArabeTests(SimpleTestCase):

    def test_une_seule_css_partagee(self):
        css = premium_base.css_arabe(libelles=True, document=True)
        self.assertNotIn('@font-face', css)
        self.assertIn('letter-spacing:0', css)
        self.assertEqual(theme.css_langue({'langue_sortie': 'ar'}),
                         premium_base.css_arabe(libelles=True))
        self.assertEqual(G._css_arabe(),
                         premium_base.css_arabe(libelles=True, document=True))

    def test_aucun_font_face_homonyme(self):
        self.assertIsNone(FONT_FACE_ARABE.search(G._css_arabe()))
        self.assertIsNone(FONT_FACE_ARABE.search(
            theme.css_langue({'langue_sortie': 'ar'})))
        html = agr_pages.build_html(_data_agricole_ar())
        self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertIn('letter-spacing:0', html)


class OnePageArabeTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='apdf6-co', nom='APDF6')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '12', '1100'),
                ('Onduleur réseau 5kW', '1', '11700'),
            ], reference='DEV-APDF6-1')

    def _html(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        data = build_quote_data(self.devis, clean_pdf_options(
            {'pdf_mode': 'onepage', 'langue_sortie': 'ar'}))
        capture = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_apdf6_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return capture.get('html', '')

    def test_onepage_ar_sans_font_face_homonyme(self):
        html = self._html()
        self.assertTrue(html)
        self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertIn('DEV-APDF6-1', html)

    @tag('pdf')
    def test_onepage_ar_chiffres_lisibles(self):
        """Texte extrait du PDF réel : la référence se relit (la superposition
        de glyphes la rendait illisible à l'extraction comme à l'œil)."""
        try:
            import fitz
        except ImportError:  # pragma: no cover
            self.skipTest('PyMuPDF absent')
        from weasyprint import HTML
        pdf = HTML(string=self._html()).write_pdf()
        doc = fitz.open(stream=pdf, filetype='pdf')
        try:
            texte = '\n'.join(p.get_text() for p in doc)
        finally:
            doc.close()
        self.assertIn('DEV-APDF6-1', texte)


# ── APDF11 — devis résidentiel premium arabe en page RTL ───────────────────
# Test-du-test : retirer ``dir="rtl"`` de ``residential/render.py`` ⇒
# ``test_ar_dir_rtl`` échoue.

def _donnees_residentiel(langue):
    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.quote_engine.residential import sample_data
    d = dict(sample_data.build("deux"))
    if langue != "fr":
        d["langue_sortie"] = langue
        d["libelles_document"] = i18n_labels.libelles(langue)
    return d


def _html_residentiel(langue):
    from apps.ventes.quote_engine.residential import render, renderer
    return render.build_html(renderer._augment(_donnees_residentiel(langue)))


class ResidentielRtlTests(SimpleTestCase):

    def test_ar_dir_rtl(self):
        html = _html_residentiel("ar")
        racine = re.search(r"<html[^>]*>", html).group(0)
        self.assertIn('dir="rtl"', racine)
        self.assertIn('lang="ar"', racine)

    def test_fr_ltr_inchange(self):
        self.assertIn("<!doctype html><html><head>", _html_residentiel("fr"))
        racine_en = re.search(r"<html[^>]*>", _html_residentiel("en")).group(0)
        self.assertEqual(racine_en, '<html lang="en">')

    @tag('pdf')
    def test_ar_trois_pages(self):
        try:
            import fitz
            from apps.ventes.quote_engine.residential import renderer
            renderer._PDF_CACHE.clear()
            pdf = renderer.render_pdf_bytes(_donnees_residentiel("ar"))
        except (ImportError, OSError):  # pragma: no cover — hôte sans libs
            self.skipTest('WeasyPrint / PyMuPDF indisponible')
        doc = fitz.open(stream=pdf, filetype='pdf')
        try:
            self.assertEqual(len(doc), 3)
            # Page 2 : le titre traduit est calé à DROITE (page RTL).
            titre = 'تفاصيل مشروعكم'
            zones = doc[1].search_for(titre)
            if zones:
                self.assertGreater(zones[0].x1, doc[1].rect.width * 0.6)
        finally:
            doc.close()
