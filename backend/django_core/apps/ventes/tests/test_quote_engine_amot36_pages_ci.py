"""AMOT36 (C-AMOT-046, volet C&I) — le PDF C&I tient son contrat de pages
(commerce 3, usine 4) quelle que soit la longueur des conditions gelées
(``cgv_ci``) :

* ``pdf_adaptatif`` mesure TOUTES les pages (``any(deborde(p))``) — la page
  équipements seule laissait passer la bande légale sous le pied ;
* au-delà, les dernières puces sont remplacées par le renvoi DÉCLARÉ
  « suite des conditions : proposition en ligne » avant tout repli.

Oracle : WeasyPrint RÉEL (positions des boîtes) et PyMuPDF (pages du PDF),
15/18/19/40 puces de 220 caractères × 2 marchés (rejoue VC ci4-ci6).

Test-du-test : remettre ``deborde(doc.pages[index_page])`` ⇒
``test_aucune_boite_sous_le_pied`` rougit (n=17-18 acceptés coupés).
"""
import copy

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.ci import blocs
from apps.ventes.quote_engine.commercial import equip
from apps.ventes.quote_engine.commercial import render as c_render
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import render as i_render
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

GABARITS = (
    ("commercial", c_sample, c_renderer, c_render, 3),
    ("industriel", i_sample, i_renderer, i_render, 4),
)


def _puces(n):
    corps = ("condition générale d'installation et de garantie " * 6)[:200]
    return [f"Puce {i:02d} — {corps}" for i in range(1, n + 1)]


def _data(sample, n):
    data = copy.deepcopy(sample.build())
    data["cgv_ci"] = _puces(n)
    return data


@tag("pdf")
class PagesCiTests(SimpleTestCase):

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover - libs natives absentes
            self.skipTest("weasyprint / PyMuPDF indisponible")

    def test_pages_tenues(self):
        import fitz
        for nom, sample, renderer, _render, pages in GABARITS:
            for n in (15, 18, 19, 40):
                with self.subTest(gabarit=nom, puces=n):
                    pdf = renderer.render_pdf_bytes(_data(sample, n))
                    doc = fitz.open(stream=pdf, filetype="pdf")
                    self.assertEqual(len(doc), pages)
                    texte = "\n".join(p.get_text() for p in doc)
                    # Le bloc d'acceptation reste imprimé.
                    self.assertIn("Puce 01", texte)

    def test_quarante_puces_renvoi_declare(self):
        import fitz
        for nom, sample, renderer, _render, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                pdf = renderer.render_pdf_bytes(_data(sample, 40))
                doc = fitz.open(stream=pdf, filetype="pdf")
                texte = " ".join(
                    " ".join(p.get_text().split()) for p in doc)
                self.assertIn("suite des conditions", texte)
                self.assertNotIn("Puce 40", texte)

    def test_aucune_boite_sous_le_pied(self):
        """Le document retenu par ``pdf_adaptatif`` n'a aucun texte sous le
        haut du pied, sur AUCUNE page (mesure WeasyPrint directe)."""
        from weasyprint import HTML
        for nom, sample, renderer, render, pages in GABARITS:
            for n in (17, 18):
                with self.subTest(gabarit=nom, puces=n):
                    d = renderer._augment(_data(sample, n))
                    retenus = []

                    def rendre(html, _retenus=retenus):
                        doc = HTML(string=html).render()
                        _retenus.append(doc)
                        return doc

                    pdf = equip.pdf_adaptatif(d, render.build_html, rendre)
                    self.assertIsNotNone(pdf)
                    tenus = [doc for doc in retenus
                             if len(doc.pages) == pages
                             and not any(equip.deborde(p) for p in doc.pages)]
                    self.assertTrue(tenus)

    def test_renvoi_trilingue(self):
        for langue in ("fr", "en", "ar"):
            self.assertTrue(blocs.RENVOI_SUITE_CONDITIONS[langue])
