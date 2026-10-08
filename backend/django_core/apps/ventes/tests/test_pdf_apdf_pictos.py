"""APDF15 (C-APDF-017) — la couverture commerciale n'imprime plus de
pictogramme emoji : un SVG en ligne pour chacune des 10 catégories.

Avant : ``commercial/categories.ICONES`` portait des emoji (« 🏪 » U+1F3EA pour
« Autre commerce »…) ; l'image backend n'a AUCUNE police emoji (``fc-list
:charset=1f3ea`` vide) et WeasyPrint imprimait un carré vide devant le titre
(sonde PLANG-5). Rendu HTML RÉEL du gabarit commercial sur les 10 catégories,
et — quand WeasyPrint est présent (image backend) — texte extrait de la page 1
du PDF réel. Le moteur ne fait que RENDRE (règle #4).
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine.commercial import categories
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample

CATEGORIES = sorted(categories.METADATA)

#: Hors plan multilingue de base (emoji), sélecteur de variante emoji, et
#: symboles « dingbats » que les polices du document n'ont pas non plus.
_SANS_POLICE = re.compile('[\U0001F000-\U0010FFFF️☀-➿]')


def _html(categorie):
    return c_render.build_html(c_renderer._augment(c_sample.build(categorie)))


class PictosCategoriesTests(SimpleTestCase):

    def test_dix_categories(self):
        self.assertEqual(len(CATEGORIES), 10)

    def test_aucun_caractere_hors_bmp(self):
        for categorie in CATEGORIES:
            with self.subTest(categorie=categorie):
                html = _html(categorie)
                self.assertEqual(_SANS_POLICE.findall(html), [])
                self.assertEqual(
                    _SANS_POLICE.findall(categories.ICONES[categorie]), [])

    def test_pictogramme_svg_devant_le_titre(self):
        for categorie in CATEGORIES:
            with self.subTest(categorie=categorie):
                icone = categories.ICONES[categorie]
                self.assertTrue(icone.startswith('<svg'), icone[:40])
                self.assertIn(f'<div class="c1c-caticon">{icone}</div>',
                              _html(categorie))

    def test_page_une_sans_glyphe_manquant(self):
        try:
            from weasyprint import HTML
        except ImportError:
            self.skipTest('WeasyPrint absent : vérifié dans l\'image backend')
        import io
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest('pypdf absent')
        for categorie in ('autre', 'hotel', 'froid'):
            with self.subTest(categorie=categorie):
                pdf = HTML(string=_html(categorie)).write_pdf()
                texte = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
                self.assertEqual(_SANS_POLICE.findall(texte), [])
