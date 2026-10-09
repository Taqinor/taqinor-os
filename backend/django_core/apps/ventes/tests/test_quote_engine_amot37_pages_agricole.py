"""AMOT37 (C-AMOT-046, volet agricole, D-AGR-2) — le document agricole tient
ses 3 pages au débordement : un contenu sous la bande de pied ou une page de
trop déclenche la densité supérieure puis un REGROUPEMENT DÉCLARÉ des lignes
(total exact) ; jamais de 4ᵉ page qui coupe le bloc d'acceptation.

WeasyPrint + PyMuPDF RÉELS (sautés sans eux), charge utile du contrat AGR2
(``test_agr310_renderer_agricole.data_complete``). Test-du-test : remettre le
rendu unique (sans ``debordement``) dans ``render_pdf_bytes`` ⇒
``test_trois_pages_jusqu_a_soixante_lignes`` échoue (4 pages à +40 lignes).
"""
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete


class RegroupementPurTests(SimpleTestCase):
    def test_ligne_regroupee_total_exact(self):
        d = renderer._augment(data_complete(nb_lignes_extra=10))
        items = pages._items(d)
        html = pages._lignes(dict(d, _regrouper_apres=4))
        self.assertIn('Autres équipements (%d lignes)' % (len(items) - 4),
                      html)
        reste = sum(it['prix_unit_ht'] * it['quantite'] for it in items[4:])
        self.assertIn(pages.fmt_centimes(reste), html)

    def test_sans_regroupement_inchange(self):
        d = renderer._augment(data_complete(nb_lignes_extra=3))
        self.assertEqual(pages._lignes(d),
                         pages._lignes(dict(d, _regrouper_apres=None)))


@tag("pdf")
class PagesAgricoleTests(SimpleTestCase):
    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover — libs natives absentes
            self.skipTest("weasyprint / PyMuPDF indisponible")

    def test_trois_pages_jusqu_a_soixante_lignes(self):
        import fitz
        for extra in (34, 40, 60):
            with self.subTest(lignes=extra):
                pdf = renderer.render_pdf_bytes(
                    data_complete(nb_lignes_extra=extra))
                doc = fitz.open(stream=pdf, filetype="pdf")
                self.assertEqual(len(doc), 3)
                page3 = doc[2].get_text()
                # Total TTC, BON POUR ACCORD et le QR sur la MÊME page 3.
                self.assertIn("TTC", page3)
                self.assertIn("BON POUR ACCORD", page3.upper())
                self.assertFalse(renderer.debordement(pdf, len(doc), 3))
