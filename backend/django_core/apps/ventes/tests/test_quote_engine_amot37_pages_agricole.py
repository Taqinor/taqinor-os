"""AMOT37 (C-AMOT-046, volet agricole) — le document agricole tient ses
3 pages (D-AGR-2) au débordement : densité supérieure, puis regroupement
DÉCLARÉ des dernières lignes ; jamais une 4ᵉ page qui coupe le bloc
d'acceptation (Total TTC, BON POUR ACCORD et QR sur la même page 3).

Rejoue VC agr7 (+34 lignes → 4 pages, page 4 = « Scannez pour signer » seul ;
+40 → « BON POUR ACCORD » en haut de la page 4). Oracle : WeasyPrint RÉEL et
PyMuPDF (pages du PDF rendu).

Test-du-test : retirer ``_document_qui_tient`` (premier rendu servi tel
quel) ⇒ ``test_trois_pages_jusqu_a_soixante_lignes`` rougit à 34 lignes.
"""
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete


@tag("pdf")
class PagesAgricoleTests(SimpleTestCase):

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover - libs natives absentes
            self.skipTest("weasyprint / PyMuPDF indisponible")

    def test_trois_pages_jusqu_a_soixante_lignes(self):
        import fitz
        for extra in (34, 40, 60):
            with self.subTest(lignes_ajoutees=extra):
                pdf = renderer.render_pdf_bytes(data_complete(extra))
                doc = fitz.open(stream=pdf, filetype="pdf")
                self.assertEqual(len(doc), 3)
                p3 = " ".join(doc[2].get_text().split()).upper()
                self.assertIn("TOTAL TTC", p3)
                self.assertIn("BON POUR ACCORD", p3)

    def test_note_calcul_ajoute_une_page_seulement(self):
        import fitz
        d = data_complete(40)
        d["include_note_calcul"] = True
        pdf = renderer.render_pdf_bytes(d)
        self.assertEqual(len(fitz.open(stream=pdf, filetype="pdf")), 4)


class RegroupementDeclareTests(SimpleTestCase):
    """Le regroupement garde Σ des lignes imprimées = Total HT."""

    def test_somme_des_lignes_egale_total_ht(self):
        d = renderer._augment(data_complete(30))
        regroupe = renderer.regrouper_lignes(d, 10)
        items = regroupe["all_items"]
        self.assertEqual(len([it for it in items
                              if it.get("regroupement")]), 1)
        somme = round(sum(it["prix_unit_ht"] * it["quantite"]
                          for it in items), 2)
        self.assertAlmostEqual(somme, d["totaux_all"]["ht_net"], places=2)
        html = pages.build_html(regroupe)
        self.assertIn("détail sur la proposition en ligne", html)

    def test_densite_minimale_imposee(self):
        d = renderer._augment(data_complete(0))
        self.assertEqual(pages.densite_compacte(d), 0)
        self.assertEqual(pages.densite_compacte(dict(d, _densite_min=2)), 2)
