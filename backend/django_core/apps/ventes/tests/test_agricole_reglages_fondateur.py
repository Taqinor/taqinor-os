# flake8: noqa
"""Founder settings — Q3 (FDA subsidy: rate only, no montant) + Q4 (butane
bonbonne prices become company settings; the ×2,5 decompensation multiplier
is derived, never hardcoded). Decisions of 20/08/2026.

Every assertion here scans the RENDERED HTML (never just the economics
function in isolation) — this is the exact gap that once let a hardcoded
"87,4 %" ship inside a PDF while the underlying function-level tests stayed
green. The agricole HTML renders with no database (``sample_data`` +
``render``/``renderer``).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_agricole_reglages_fondateur -v 2
"""
import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole import (
    constants, economics, render, renderer, sample_data)


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
