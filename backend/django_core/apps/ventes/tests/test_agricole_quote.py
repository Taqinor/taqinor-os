"""Tests for the premium AGRICOLE (pompage solaire) quote engine.

Covers renderer selection, the solar-vs-butane-vs-diesel economics (incl. the
"solar burns no fuel" rule and the FDA subsidy), the toggleable persuasion
sections, the no-invented-number guard (curve-less pump), and the 5-page render.

The content/economics tests need no DB and no WeasyPrint; the page-count test
renders a real PDF (WeasyPrint, available in CI/Docker).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_agricole_quote -v 2
"""
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import (
    economics, render, renderer, sample_data)
from apps.ventes.quote_engine.builder import clean_pdf_options


class _Devis:
    """Tiny stand-in so we can test selection without the ORM."""
    def __init__(self, mode):
        self.mode_installation = mode


class TestAgricoleSelection(SimpleTestCase):
    def test_full_agricole_selected(self):
        self.assertTrue(renderer.is_agricultural(_Devis("agricole"), {"pdf_mode": "full"}))
        self.assertTrue(renderer.is_agricultural(_Devis("agricole"), None))  # default full

    def test_onepage_agricole_falls_back(self):
        self.assertFalse(renderer.is_agricultural(_Devis("agricole"), {"pdf_mode": "onepage"}))

    def test_other_modes_not_agricole(self):
        self.assertFalse(renderer.is_agricultural(_Devis("residentiel"), {"pdf_mode": "full"}))
        self.assertFalse(renderer.is_agricultural(_Devis("industriel"), {"pdf_mode": "full"}))


class TestCleanPdfOptionsAgricole(SimpleTestCase):
    def test_toggles_and_fuel_whitelisted(self):
        opts = clean_pdf_options({
            "show_subsidy": False, "show_fuel_comparison": False,
            "show_environmental": False, "show_schematic": False,
            "show_water_yield": False, "current_fuel": "diesel"})
        self.assertFalse(opts["show_subsidy"])
        self.assertFalse(opts["show_fuel_comparison"])
        self.assertEqual(opts["current_fuel"], "diesel")

    def test_defaults_on(self):
        opts = clean_pdf_options({})
        for k in ("show_subsidy", "show_fuel_comparison", "show_environmental",
                  "show_schematic", "show_water_yield"):
            self.assertTrue(opts[k])
        self.assertIsNone(opts["current_fuel"])

    def test_bad_fuel_ignored(self):
        self.assertIsNone(clean_pdf_options({"current_fuel": "nuclear"})["current_fuel"])


class TestAgricoleEconomics(SimpleTestCase):
    def setUp(self):
        self.data = sample_data.build("agrumes")  # butane, curve pump

    def test_solar_has_no_fuel_cost(self):
        eco = economics.compute(self.data)
        self.assertEqual(eco["fuel_costs"]["solaire"], 0)

    def test_decompensation_makes_butane_worse(self):
        eco = economics.compute(self.data)
        self.assertGreater(eco["fuel_costs"]["butane_future"],
                           eco["fuel_costs"]["butane_today"])

    def test_saving_is_full_fuel_bill(self):
        eco = economics.compute(self.data)
        # Solar burns no fuel -> annual saving equals the whole butane bill.
        self.assertEqual(eco["saving_vs_butane"], eco["fuel_costs"]["butane_today"])
        self.assertEqual(eco["annual_saving"], eco["fuel_costs"]["butane_today"])

    def test_payback_positive_and_reasonable(self):
        eco = economics.compute(self.data)
        self.assertIsNotNone(eco["payback"])
        self.assertGreater(eco["payback"], 0)
        self.assertLess(eco["payback"], 25)

    def test_fda_subsidy_capped(self):
        eco = economics.compute(self.data)
        self.assertGreater(eco["fda_amount"], 0)
        self.assertLessEqual(eco["fda_amount"], eco["fda_cap"])
        self.assertEqual(eco["net_after_fda"], eco["quote_ttc"] - eco["fda_amount"])

    def test_diesel_reference_when_chosen(self):
        data = sample_data.build("dattier")  # current_fuel = diesel
        eco = economics.compute(data)
        self.assertEqual(eco["current_fuel"], "diesel")
        self.assertEqual(eco["annual_saving"], eco["fuel_costs"]["diesel"])
        self.assertIn("gasoil", eco["fuel_qty_label"])

    def test_curveless_pump_invents_nothing(self):
        data = sample_data.build("agrumes")
        data["etude"]["m3_jour"] = None  # no curve -> no water
        eco = economics.compute(data)
        self.assertFalse(eco["has_water"])
        self.assertEqual(eco["annual_m3"], 0)
        self.assertEqual(eco["fuel_costs"]["butane_today"], 0)
        self.assertIsNone(eco["payback"])


class TestAgricoleRender(SimpleTestCase):
    def _html(self, key="agrumes", **opts):
        data = sample_data.build(key)
        data.update(opts)
        return render.build_html(renderer._augment(data))

    def test_four_page_roots_present(self):
        html = self._html()
        for cls in ("a1-root", "a2-root", "a3-root", "a4-root"):
            self.assertIn(cls, html)

    def test_key_content_present(self):
        html = self._html()
        self.assertIn("0 carburant", html)
        self.assertIn("Subvention FDA", html)
        self.assertIn("bon marché tant qu", html)        # butane punch line
        self.assertIn("Bon pour accord", html)
        self.assertIn("<svg", html)                       # schematic
        self.assertIn("data:image/png;base64", html)      # charts

    def test_margin_never_leaks(self):
        html = self._html().lower()
        self.assertNotIn("prix_achat", html)
        self.assertNotIn("marge", html)

    def test_subsidy_toggle_hides_block(self):
        self.assertNotIn("Subvention FDA", self._html(show_subsidy=False))

    def test_fuel_toggle_hides_comparison(self):
        self.assertNotIn("bon marché tant qu", self._html(show_fuel_comparison=False))

    def test_renders_all_scenarios(self):
        for key in sample_data.keys():
            self.assertIn("a1-root", self._html(key))


@tag("weasyprint")
class TestAgricolePageCount(SimpleTestCase):
    """Real PDF render — exactly 4 A4 pages (WeasyPrint, CI/Docker)."""
    def test_four_pages(self):
        try:
            import weasyprint  # noqa: F401
        except Exception:  # pragma: no cover - skip where native libs absent
            self.skipTest("weasyprint native libs unavailable")
        from weasyprint import HTML
        for key in sample_data.keys():
            data = renderer._augment(sample_data.build(key))
            doc = HTML(string=render.build_html(data)).render()
            self.assertEqual(len(doc.pages), 4, f"{key} not 4 pages")
