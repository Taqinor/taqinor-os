"""AMOT36 (C-AMOT-046, volet C&I) — le PDF C&I tient son contrat de pages
(commerce 3, usine 4) : ``pdf_adaptatif`` mesure TOUTES les pages, la liste
variable des conditions est tronquée avec renvoi déclaré (« Suite des
conditions : proposition en ligne ») avant tout refus, et aucun repli legacy
n'est servi à un devis C&I dont le contrat de pages est intenable.

WeasyPrint + PyMuPDF RÉELS (sautés sans eux). Test-du-test : remettre
``deborde(doc.pages[index_page])`` dans ``pdf_adaptatif`` ⇒
``test_contrat_de_pages`` échoue (puces sous le pied, ou page de trop).
"""
import copy

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.ci import blocs
from apps.ventes.quote_engine.commercial import equip
from apps.ventes.quote_engine.commercial import renderer as c_renderer
from apps.ventes.quote_engine.commercial import sample_data as c_sample
from apps.ventes.quote_engine.industriel import renderer as i_renderer
from apps.ventes.quote_engine.industriel import sample_data as i_sample

GABARITS = (("commercial", c_sample, c_renderer, 3),
            ("industriel", i_sample, i_renderer, 4))
_SUITE = "Suite des conditions : proposition en ligne"


def _puces(n):
    return [(f"Condition contractuelle n° {i:02d} — " + "texte " * 40)[:220]
            for i in range(1, n + 1)]


class TroncatureDeclareeTests(SimpleTestCase):
    def test_puces_tronquees_avec_renvoi(self):
        d = {"cgv_ci": _puces(10), "_cgv_max": 3}
        puces = blocs.puces_conditions(d)
        self.assertEqual(len(puces), 4)
        self.assertEqual(puces[-1], _SUITE)

    def test_sans_troncature_inchange(self):
        self.assertEqual(blocs.puces_conditions({"cgv_ci": _puces(5)}),
                         _puces(5))


@tag("pdf")
class PagesCiTests(SimpleTestCase):
    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover — libs natives absentes
            self.skipTest("weasyprint / PyMuPDF indisponible")

    def _rendre(self, sample, renderer, n):
        import fitz
        data = copy.deepcopy(sample.build())
        data["cgv_ci"] = _puces(n)
        pdf = renderer.render_pdf_bytes(data)
        return fitz.open(stream=pdf, filetype="pdf")

    def test_contrat_de_pages(self):
        for nom, sample, renderer, pages in GABARITS:
            for n in (15, 18, 19, 40):
                with self.subTest(gabarit=nom, puces=n):
                    doc = self._rendre(sample, renderer, n)
                    self.assertEqual(len(doc), pages)
                    for page in doc:
                        pied = page.rect.height * (1 - equip.PIED_MM / 297.0)
                        for bloc in page.get_text("blocks"):
                            x0, y0, x1, y1 = bloc[:4]
                            # Aucun bloc de texte ne CHEVAUCHE le haut du pied.
                            self.assertFalse(y0 < pied - 1 and y1 > pied + 1,
                                             (nom, n, bloc[4][:60]))

    def test_quarante_puces_renvoi_imprime(self):
        for nom, sample, renderer, _pages in GABARITS:
            with self.subTest(gabarit=nom):
                doc = self._rendre(sample, renderer, 40)
                texte = " ".join(page.get_text() for page in doc)
                self.assertIn("Suite des conditions", texte)
