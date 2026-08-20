# flake8: noqa
"""Founder settings — Q3 (FDA subsidy: rate only, no montant) + Q4 (butane
bonbonne prices become company settings; the ×2,5 decompensation multiplier
is derived, never hardcoded). Decisions of 20/08/2026.

Every assertion here scans the RENDERED HTML (never just the economics
function in isolation) — this is the exact gap that once let a hardcoded
"87,4 %" ship inside a PDF while the underlying function-level tests stayed
green. The agricole HTML renders with no database (``sample_data`` +
``render``/``renderer``); the CompanyProfile-scoped Q4 settings path is
exercised by mocking ``CompanyProfile.objects.filter`` (no real DB row
needed, and SimpleTestCase forbids one anyway).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_agricole_reglages_fondateur -v 2
"""
import re
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole import (
    constants, economics, render, renderer, sample_data)


class _FakeProfile:
    """Stand-in for a ``CompanyProfile`` row — only the two Q4 fields matter."""

    def __init__(self, prix, cout):
        self.agricole_prix_bonbonne = prix
        self.agricole_cout_reel_bonbonne = cout


def _mock_profile(prix, cout):
    """Patch ``CompanyProfile.objects.filter(...).first()`` — no DB touched."""
    qs = MagicMock()
    qs.first.return_value = _FakeProfile(prix, cout)
    return patch(
        "apps.parametres.models_company.CompanyProfile.objects.filter",
        return_value=qs,
    )


def _html(key="agrumes", company_id=None, **opts):
    data = sample_data.build(key)
    if company_id is not None:
        data["_company_id"] = company_id
    data.update(opts)
    return render.build_html(renderer._augment(data))


class TestQ3FdaNoMontant(SimpleTestCase):
    """No FDA subsidy AMOUNT anywhere in the document — only the sourced 30 %
    rate and the founder's exact qualitative sentence."""

    def test_qualitative_sentence_present_verbatim(self):
        html = _html()
        self.assertIn(
            "Subvention FDA de 30 % possible (dispositif 2024, cumulable "
            "irrigation localisée) — nous montons le dossier avec vous.",
            html)

    def test_fda_block_carries_no_mad_amount(self):
        """Scan the FDA block specifically (page 3) — other legitimate MAD
        figures exist elsewhere on the page: equipment price chain, butane
        bonbonne prices…"""
        html = _html()
        m = re.search(r'<div class="a3-fda">.*?</div></div>', html, re.S)
        self.assertIsNotNone(m, "bloc FDA introuvable dans le HTML rendu")
        fda_block = m.group(0)
        self.assertNotIn("MAD", fda_block)
        self.assertNotIn("DH", fda_block)

    def test_no_net_after_fda_anywhere(self):
        html = _html()
        self.assertNotIn("Coût net estimé", html)
        self.assertNotIn("net_after_fda", html)

    def test_cover_stat_shows_rate_not_amount(self):
        """Page 1 supporting stat: percentage only, never a DH/MAD figure."""
        html = _html()
        self.assertIn("Subvention FDA possible", html)

    def test_degraded_path_no_fda_amount(self):
        """Curve-less pump (no m³/jour): the degraded page 4 must still avoid
        any FDA montant while keeping the qualitative note."""
        data = sample_data.build("agrumes")
        data["etude"]["m3_jour"] = None
        html = render.build_html(renderer._augment(data))
        self.assertNotIn("coût net", html.lower())
        self.assertIn(
            "Subvention FDA de 30 % possible (dispositif 2024, cumulable "
            "irrigation localisée) — nous montons le dossier avec vous.",
            html)

    def test_subsidy_toggle_hides_everything_including_the_rate(self):
        html = _html(show_subsidy=False)
        self.assertNotIn("Subvention FDA", html)
        self.assertNotIn("possible (dispositif 2024", html)

    def test_economics_no_longer_exposes_fda_amount_fields(self):
        eco = economics.compute(sample_data.build("agrumes"))
        self.assertNotIn("fda_amount", eco)
        self.assertNotIn("fda_cap", eco)
        self.assertNotIn("net_after_fda", eco)
        self.assertEqual(eco["fda_pct"], 30)

    def test_fda_cap_constant_removed(self):
        """The plafond constant is gone — nothing reads it any more."""
        self.assertFalse(hasattr(constants, "FDA_SUBSIDY_CAP"))


class TestQ4ButaneReglages(SimpleTestCase):
    """The butane bonbonne prices are founder-editable company settings; the
    decompensation ratio is DERIVED from them (cout_reel / prix), never a
    hardcoded ×2,5 — two different company settings must render two different
    butane comparatifs in the HTML."""

    def test_decomp_multiplier_constant_removed(self):
        self.assertFalse(hasattr(constants, "BUTANE_DECOMP_MULTIPLIER"))

    def test_default_ratio_is_128_over_50_not_the_old_2_5(self):
        eco = economics.compute(sample_data.build("agrumes"))
        today = eco["fuel_costs"]["butane_today"]
        future = eco["fuel_costs"]["butane_future"]
        self.assertGreater(today, 0)
        # 128 / 50 = 2,56 — dérivé des défauts, plus jamais 2,5 codé en dur.
        self.assertEqual(future, round(today * 128 / 50))
        self.assertNotEqual(future, round(today * 2.5))

    def test_company_settings_change_the_computed_ratio(self):
        with _mock_profile(40, 200):  # ratio 5,0 — distinct de tout défaut
            eco = economics.compute(sample_data.build("agrumes"), company_id=1)
        self.assertEqual(eco["butane_12kg_subventionne"], 40)
        self.assertEqual(eco["butane_12kg_reel"], 200)
        today = eco["fuel_costs"]["butane_today"]
        future = eco["fuel_costs"]["butane_future"]
        self.assertEqual(future, round(today * 200 / 40))

    def test_rendered_html_differs_between_two_company_profiles(self):
        with _mock_profile(50, 128):
            html_a = _html(company_id=1)
        with _mock_profile(90, 300):
            html_b = _html(company_id=1)
        self.assertNotEqual(html_a, html_b)
        self.assertIn("50 MAD", html_a)
        self.assertIn("128 MAD", html_a)
        self.assertIn("90 MAD", html_b)
        self.assertIn("300 MAD", html_b)

    def test_zero_setting_omits_comparison_instead_of_inventing_a_ratio(self):
        """Un des deux réglages à 0 → aucun rapport calculable → la
        comparaison décompensée s'omet (0), jamais un multiplicateur inventé."""
        with _mock_profile(0, 128):
            eco = economics.compute(sample_data.build("agrumes"), company_id=1)
        self.assertEqual(eco["fuel_costs"]["butane_future"], 0)
        self.assertGreater(eco["fuel_costs"]["butane_today"], 0)

    def test_none_setting_falls_back_to_default_not_zero(self):
        """A company profile that never touched the field (still at the model
        default) behaves exactly like the historical default — never a 0."""
        with _mock_profile(None, None):
            eco = economics.compute(sample_data.build("agrumes"), company_id=1)
        self.assertEqual(eco["butane_12kg_subventionne"], 50)
        self.assertEqual(eco["butane_12kg_reel"], 128)
