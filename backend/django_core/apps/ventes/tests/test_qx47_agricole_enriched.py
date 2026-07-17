"""QX47 — Devis AGRICOLE enrichi : graphe « eau livrée vs besoin culture (ETc
mensuel, moteur QX48) » + bassin recommandé (1-3× le besoin journalier, jours
d'autonomie). La subvention FDA et le comparatif diesel/butane existaient déjà.

Le rendu dégrade proprement sans données d'exploitation (repli sur le strip
carburant historique) et reste 4 pages. NE réintroduit PAS les anciens
graphiques mensuels (test_no_monthly_bar_graph : « mois par mois » + clés
build_all water/production restent absents).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qx47_agricole_enriched -v 2
"""
from django.test import SimpleTestCase

from apps.ventes.quote_engine.agricole import (
    charts, render, renderer, sample_data)


class TestAgronomyMonthlyInAugment(SimpleTestCase):
    def test_monthly_need_computed_with_farm_data(self):
        d = renderer._augment(sample_data.build("agrumes"))
        self.assertEqual(len(d.get("monthly_need_m3day") or []), 12)
        self.assertEqual(len(d.get("etc_mm_day") or []), 12)

    def test_monthly_need_none_without_farm_data(self):
        base = sample_data.build("agrumes")
        base["etude"] = dict(base["etude"])
        base["etude"].pop("crop", None)
        base["etude"].pop("surface_ha", None)
        d = renderer._augment(base)
        self.assertIsNone(d.get("monthly_need_m3day"))

    def test_bassin_recommended_two_times_peak(self):
        d = renderer._augment(sample_data.build("agrumes"))
        besoin = d.get("besoin_m3j")
        self.assertTrue(besoin and besoin > 0)
        self.assertEqual(d["bassin_reco_m3"], round(besoin * 2))
        self.assertEqual(d["bassin_min_m3"], round(besoin))
        self.assertEqual(d["bassin_max_m3"], round(besoin * 3))
        self.assertEqual(d["bassin_autonomie_j"], 2)


class TestAgricoleEnrichedRender(SimpleTestCase):
    def _html(self, key="agrumes", **opts):
        data = sample_data.build(key)
        data.update(opts)
        return render.build_html(renderer._augment(data))

    def test_still_four_page_roots(self):
        html = self._html()
        for cls in ("a1-root", "a2-root", "a3-root", "a4-root"):
            self.assertIn(cls, html)

    def test_monthly_water_vs_need_chart_present(self):
        html = self._html()
        self.assertIn("face à l'eau livrée", html)      # header du graphe QX47
        self.assertIn("FAO-56 par mois", html)          # légende
        self.assertIn("eau livrée", html)

    def test_bassin_block_present_with_autonomy(self):
        html = self._html()
        self.assertIn("Bassin de stockage recommandé", html)
        self.assertIn("jours d'autonomie", html)

    def test_degrades_without_farm_data(self):
        base = sample_data.build("agrumes")
        base["etude"] = dict(base["etude"])
        base["etude"].pop("crop", None)
        base["etude"].pop("surface_ha", None)
        html = render.build_html(renderer._augment(base))
        # pas de graphe (repli sur le strip carburant), toujours 4 pages
        self.assertNotIn("face à l'eau livrée", html)
        self.assertIn("carburant", html)
        for cls in ("a1-root", "a2-root", "a3-root", "a4-root"):
            self.assertIn(cls, html)

    def test_fda_and_fuel_still_present(self):
        html = self._html()
        self.assertIn("Subvention FDA", html)       # (c) déjà là
        self.assertIn("carburant", html)            # (d) déjà là

    def test_no_old_monthly_bar_graph_reintroduced(self):
        html = self._html()
        self.assertNotIn("mois par mois", html)
        keys = set(charts.build_all(renderer._augment(sample_data.build("agrumes"))))
        self.assertNotIn("water", keys)
        self.assertNotIn("production", keys)

    def test_no_margin_leak(self):
        html = self._html().lower()
        self.assertNotIn("prix_achat", html)
        self.assertNotIn("marge", html)
