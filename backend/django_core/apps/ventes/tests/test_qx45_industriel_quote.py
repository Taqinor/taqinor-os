"""QX45 — Renderer INDUSTRIEL (CFO) dédié.

Couvre la sélection (full/premium seulement, jamais one-page ; jamais un autre
mode), le contenu CFO (baseline, cashflow, payback, TRI, ISO 50001/CBAM,
garanties, signature), le TRI (vrai calcul actuariel), la garde rule #4
(prix_achat/marge jamais rendus) et le rendu 3 pages (WeasyPrint, CI/Docker).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx45_industriel_quote -v 2
"""
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.industriel import (
    render, renderer, sample_data)
from apps.ventes.quote_engine.industriel.finance import irr_flat


class _Devis:
    """Stand-in minimal pour tester la sélection sans l'ORM."""
    def __init__(self, mode):
        self.mode_installation = mode


class TestIndustrielSelection(SimpleTestCase):
    def test_full_industriel_selected(self):
        self.assertTrue(renderer.is_industrial(_Devis("industriel"), {"pdf_mode": "full"}))
        self.assertTrue(renderer.is_industrial(_Devis("industriel"), None))  # défaut full

    def test_onepage_industriel_falls_back(self):
        self.assertFalse(renderer.is_industrial(_Devis("industriel"), {"pdf_mode": "onepage"}))

    def test_other_modes_not_industriel(self):
        self.assertFalse(renderer.is_industrial(_Devis("residentiel"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_industrial(_Devis("agricole"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_industrial(_Devis("commercial"), {"pdf_mode": "full"}))


class TestIndustrielContent(SimpleTestCase):
    def setUp(self):
        self.data = renderer._augment(sample_data.build())
        self.html = render.build_html(self.data)

    def test_three_page_content_present(self):
        self.assertEqual(self.html.count('class="page"'), 3)

    def test_cfo_blocks_present(self):
        self.assertIn("Baseline énergétique", self.html)   # P1
        self.assertIn("Cashflow cumulé", self.html)         # P2
        self.assertIn("TRI sur", self.html)                 # P2
        self.assertIn("ISO 50001", self.html)               # P3
        self.assertIn("CBAM", self.html)                    # P3
        self.assertIn("Bon pour accord", self.html)         # P3 signature

    def test_autoconso_honesty_no_peak_promise(self):
        # jamais promettre la pointe sans batterie
        self.assertIn("autoconsommation", self.html.lower())
        self.assertIn("pointe", self.html.lower())

    def test_injection_omitted_without_data(self):
        # sans injection calculée (QX50), aucune ligne d'injection inventée
        self.assertNotIn("surplus injecté", self.html)

    def test_rule4_no_buy_price_or_margin(self):
        # RULE #4 / prix_achat jamais client-facing
        self.assertNotIn("prix_achat", self.html)
        self.assertNotIn("prix_achat", self.html.lower())
        self.assertNotIn("marge", self.html.lower())


class TestIndustrielInjectionWhenPresent(SimpleTestCase):
    def test_injection_line_rendered_with_mention(self):
        base = sample_data.build()
        base["etude"] = dict(base["etude"])
        base["etude"]["injection_dh_an"] = 30000
        base["etude"]["injection_kwh_an"] = 45000
        html = render.build_html(renderer._augment(base))
        self.assertIn("surplus injecté", html)
        self.assertIn("82-21", html)
        self.assertIn("plafond 20 %", html)
        self.assertIn("ANRE 03/2026", html)


class TestIndustrielUnsupported(SimpleTestCase):
    def test_no_priced_lines_unsupported(self):
        base = sample_data.build()
        base["all_items"] = [{"designation": "x", "quantite": 0}]
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(base)

    def test_no_investment_unsupported(self):
        base = sample_data.build()
        base["display_total"] = 0
        base["totaux_all"] = {"ttc": 0}
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(base)


class TestIrrFlat(SimpleTestCase):
    def test_positive_irr(self):
        # 1,75 M investis, 420 k/an sur 15 ans → TRI ~22-24 %
        tri = irr_flat(1_750_000, 420_000, 15)
        self.assertIsNotNone(tri)
        self.assertGreater(tri, 15)
        self.assertLess(tri, 30)

    def test_degenerate_returns_none(self):
        self.assertIsNone(irr_flat(0, 420_000))
        self.assertIsNone(irr_flat(1_750_000, 0))
        self.assertIsNone(irr_flat(1_750_000, 420_000, 0))


@tag("weasyprint")
class TestIndustrielPageCount(SimpleTestCase):
    """Rendu PDF réel — exactement 3 pages A4 (WeasyPrint, CI/Docker)."""
    def test_three_pages(self):
        try:
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover - skip where native libs absent
            self.skipTest("weasyprint native libs unavailable")
        data = renderer._augment(sample_data.build())
        pdf = renderer.render_pdf_bytes(data)
        self.assertTrue(pdf[:4] == b"%PDF")
        from weasyprint import HTML
        doc = HTML(string=render.build_html(data)).render()
        self.assertEqual(len(doc.pages), 3)
