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

    def test_fda_subsidy_rate_only_no_amount(self):
        """Q3 (fondateur, 20/08/2026) — le plafond FDA n'est pas confirmable :
        seul le TAUX est exposé, plus aucun montant en MAD. Voir
        test_agricole_reglages_fondateur.py pour le scan du document rendu."""
        eco = economics.compute(self.data)
        self.assertEqual(eco["fda_pct"], 30)
        self.assertNotIn("fda_amount", eco)
        self.assertNotIn("fda_cap", eco)
        self.assertNotIn("net_after_fda", eco)

    def test_diesel_reference_when_chosen(self):
        data = sample_data.build("dattier")  # current_fuel = diesel
        eco = economics.compute(data)
        self.assertEqual(eco["current_fuel"], "diesel")
        self.assertEqual(eco["annual_saving"], eco["fuel_costs"]["diesel"])
        # QJR151(b) — sans dépense carburant saisie, la consommation actuelle
        # est INCONNUE : plus de quantité de carburant évitée (elle était
        # modélisée sur le CV de la pompe solaire NEUVE).
        self.assertEqual(eco["fuel_qty_label"], "")
        data["etude"]["fuel_spend_current"] = 54000
        self.assertIn("gasoil", economics.compute(data)["fuel_qty_label"])

    def test_curveless_pump_invents_nothing(self):
        data = sample_data.build("agrumes")
        data["etude"]["m3_jour"] = None  # no curve -> no water
        eco = economics.compute(data)
        self.assertFalse(eco["has_water"])
        self.assertEqual(eco["annual_m3"], 0)
        self.assertEqual(eco["fuel_costs"]["butane_today"], 0)
        self.assertIsNone(eco["payback"])

    def test_peak_water_need_from_fao56(self):
        """The farm's real peak need (FAO-56) is computed and the pump covers it."""
        eco = economics.compute(self.data)  # 2 ha agrumes · souss-massa · goutte
        self.assertIsNotNone(eco["besoin_m3j"])
        self.assertGreater(eco["besoin_m3j"], 0)
        self.assertGreaterEqual(self.data["etude"]["m3_jour"], eco["besoin_m3j"])

    def test_no_farm_data_means_no_invented_need(self):
        data = sample_data.build("agrumes")
        for k in ("crop", "surface_ha", "region", "irrigation_method"):
            data["etude"].pop(k, None)
        self.assertIsNone(economics.compute(data)["besoin_m3j"])

    # ── QJR150 — « Aucune énergie actuelle / nouveau forage » ────────────────
    def test_aucune_energie_actuelle_na_ni_economie_ni_payback(self):
        data = sample_data.build("agrumes")
        data["etude"]["current_fuel"] = "none"
        eco = economics.compute(data)
        self.assertEqual(eco["annual_fuel_now"], 0)
        self.assertEqual(eco["annual_saving"], 0)
        self.assertEqual(eco["savings_20y"], 0)
        self.assertEqual(eco["saving_vs_butane"], 0)
        self.assertEqual(eco["saving_vs_diesel"], 0)
        self.assertIsNone(eco["payback"])
        self.assertIsNone(eco["payback_butane"])
        self.assertIsNone(eco["payback_diesel"])

    def test_aucune_energie_garde_la_comparaison_de_marche(self):
        """La comparaison solaire/butane/diesel est un coût de MARCHÉ, pas la
        facture du client : elle reste calculée (elle n'est pas publiée comme
        une économie)."""
        data = sample_data.build("agrumes")
        data["etude"]["current_fuel"] = "none"
        eco = economics.compute(data)
        self.assertGreater(eco["fuel_costs"]["butane_today"], 0)
        self.assertGreater(eco["fuel_costs"]["diesel"], 0)

    def test_depense_saisie_ne_ressuscite_pas_une_economie_sans_carburant(self):
        """Deux champs indépendants qui se contredisent → on ne publie rien."""
        data = sample_data.build("agrumes")
        data["etude"]["current_fuel"] = "none"
        data["etude"]["fuel_spend_current"] = 40000
        eco = economics.compute(data)
        self.assertEqual(eco["annual_fuel_now"], 0)
        self.assertEqual(eco["annual_saving"], 0)
        self.assertIsNone(eco["payback"])

    # ── QJR151 — les hypothèses forfaitaires sont dites, ou rien n'est publié ─
    def test_jours_et_ratio_de_pompage_sont_saisissables(self):
        data = sample_data.build("agrumes")
        defaut = economics.compute(data)
        data["etude"]["jours_pompage_an"] = 260      # 5 jours/semaine
        data["etude"]["ratio_pointe_moyenne"] = 0.5
        saisi = economics.compute(data)
        self.assertEqual(saisi["pumping_days_per_year"], 260)
        self.assertEqual(saisi["peak_to_avg"], 0.5)
        self.assertLess(saisi["annual_m3"], defaut["annual_m3"])
        # ce que la saisie change en cascade : facture, économie, amortissement
        self.assertLess(saisi["fuel_costs"]["butane_today"],
                        defaut["fuel_costs"]["butane_today"])
        self.assertLess(saisi["annual_saving"], defaut["annual_saving"])
        self.assertGreater(saisi["payback"], defaut["payback"])

    def test_hypothese_de_pompage_est_publiee(self):
        data = sample_data.build("agrumes")
        eco = economics.compute(data)
        self.assertEqual(eco["pumping_days_per_year"], 300)
        self.assertEqual(eco["peak_to_avg"], 0.62)

    def test_impact_environnemental_exige_la_consommation_actuelle(self):
        """Les bonbonnes/CO₂ évités viennent de la dépense RÉELLE du client, pas
        du CV de la pompe solaire NEUVE (qui n'a jamais brûlé un litre)."""
        data = sample_data.build("agrumes")
        eco = economics.compute(data)             # aucune dépense saisie
        self.assertEqual(eco["co2_t"], 0)
        self.assertEqual(eco["fuel_qty_label"], "")
        data["etude"]["fuel_spend_current"] = 40000
        eco2 = economics.compute(data)
        self.assertGreater(eco2["co2_t"], 0)
        self.assertIn("bonbonnes", eco2["fuel_qty_label"])
        # 40 000 MAD / 50 MAD la bonbonne = 800 bonbonnes — une DÉRIVATION de la
        # dépense saisie, jamais un modèle sur le CV de la pompe neuve.
        self.assertIn("800", eco2["fuel_qty_label"])

    def test_impact_ne_depend_plus_du_cv_de_la_pompe_neuve(self):
        data = sample_data.build("agrumes")
        data["etude"]["fuel_spend_current"] = 40000
        base = economics.compute(data)["co2_t"]
        data["etude"]["pompe_cv"] = "15"          # pompe deux fois plus grosse
        self.assertEqual(economics.compute(data)["co2_t"], base)

    def test_hectares_seulement_si_surface_renseignee(self):
        data = sample_data.build("agrumes")
        self.assertEqual(economics.compute(data)["hectares_irrigable"], 2.0)
        data["etude"].pop("surface_ha", None)     # champ optionnel, souvent vide
        self.assertIsNone(economics.compute(data)["hectares_irrigable"])
        data["etude"]["surface_ha"] = 0
        self.assertIsNone(economics.compute(data)["hectares_irrigable"])

    def test_real_fuel_bill_overrides_model(self):
        """A captured current fuel spend (MAD/an) drives savings & payback."""
        data = sample_data.build("agrumes")
        data["etude"]["fuel_spend_current"] = 40000
        eco = economics.compute(data)
        self.assertEqual(eco["annual_fuel_now"], 40000)
        self.assertEqual(eco["annual_saving"], 40000)


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
        self.assertIn("carburant", html)                  # the sun-is-your-fuel framing
        self.assertIn("économisez", html.lower())         # money co-hero
        self.assertIn("Subvention FDA", html)
        self.assertIn("bon marché tant qu", html)         # butane punch line
        self.assertIn("Bon pour accord", html)
        self.assertIn("<svg", html)                       # schematic + icons
        self.assertIn("data:image/png;base64", html)      # fuel / payback charts

    def test_no_monthly_bar_graph(self):
        """Founder + research: the monthly water/production bar graphs are gone."""
        html = self._html()
        self.assertNotIn("mois par mois", html)
        from apps.ventes.quote_engine.agricole import charts
        keys = set(charts.build_all(renderer._augment(sample_data.build("agrumes"))))
        self.assertNotIn("water", keys)
        self.assertNotIn("production", keys)

    def test_two_heroes_and_tangible_water(self):
        """Page 1 leads with water + money; water is made tangible (bidons)."""
        html = self._html()
        self.assertIn("bidons", html)                     # jerrycan equivalence
        self.assertIn("économisez", html.lower())         # money co-hero

    def test_lift_translated_to_farmer_language(self):
        """HMT is shown as a building height, never a bare acronym headline."""
        self.assertIn("immeuble", self._html())

    def test_reassurance_water_all_year(self):
        self.assertIn("toute l", self._html())            # "De l'eau toute l'année"

    def test_abh_authorisation_guardrail_present(self):
        self.assertIn("ABH", self._html())

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

    # ── QJR151 — la page 4 dit son hypothèse ; page 1 n'invente pas d'hectares ─
    def test_hypothese_de_pompage_imprimee_sous_le_graphe(self):
        html = self._html()
        self.assertIn("Hypothèse de calcul", html)
        self.assertIn("300 jours de pompage par an", html)
        self.assertIn("62 %", html)

    def test_bandeau_environnemental_omis_sans_consommation_actuelle(self):
        self.assertNotIn("évitées/an", self._html())

    def test_bandeau_environnemental_publie_avec_la_depense_reelle(self):
        data = sample_data.build("agrumes")
        data["etude"]["fuel_spend_current"] = 40000
        html = render.build_html(renderer._augment(data))
        self.assertIn("évitées/an", html)
        self.assertIn("800 bonbonnes de butane", html)

    def test_pastille_hectares_omise_sans_surface(self):
        data = sample_data.build("agrumes")
        data["etude"].pop("surface_ha", None)
        html = render.build_html(renderer._augment(data))
        self.assertNotIn("de cultures irriguées", html)
        self.assertIn("de cultures irriguées", self._html())   # surface connue

    # ── QJR150 — « nouveau forage » : aucun montant d'économie sur le document ─
    def test_nouveau_forage_ne_publie_aucun_montant_deconomie(self):
        data = sample_data.build("agrumes")
        data["etude"]["current_fuel"] = "none"
        html = render.build_html(renderer._augment(data))
        # la page 4 bascule sur la branche dégradée, sans économie ni payback
        self.assertIn("Zéro carburant", html)
        self.assertNotIn("économisés sur 20 ans", html)
        self.assertNotIn("de butane économisé", html)
        self.assertNotIn("MAD/an", html)
        # la page 1 sert son héros « Votre carburant · 0 DH », pas un montant
        self.assertNotIn("en ne payant plus", html)
        self.assertIn("Votre carburant", html)
        self.assertNotIn("Le jour où le solaire vous rembourse", html)
        # aucun des montants modélisés sur une facture de butane non payée
        eco = economics.compute(sample_data.build("agrumes"))
        from apps.ventes.quote_engine.agricole import theme as a_theme
        for montant in (eco["fuel_costs"]["butane_today"],
                        eco["fuel_costs"]["butane_today"] * 20):
            self.assertNotIn(f"{a_theme.fmt(montant)} MAD", html)
            self.assertNotIn(f"{a_theme.fmt(montant)}<span", html)

    # ── QJR149 — validité : jamais « None jours », jamais un 30 forfaitaire ───
    def _html_sans_validite(self):
        """Le cas réel : ``builder`` n'a pas pu calculer la validité (devis sans
        date de création, ou date de validité ≤ création) → ``renderer._augment``
        pose ``validity_days``/``valid_until`` à None."""
        data = sample_data.build("agrumes")
        data.pop("validity_days", None)
        data.pop("valid_until", None)
        augmented = renderer._augment(data)
        self.assertIsNone(augmented["validity_days"])
        self.assertIsNone(augmented["valid_until"])
        return render.build_html(augmented)

    def test_validite_indeterminable_nimprime_pas_none(self):
        html = self._html_sans_validite()
        self.assertNotIn("None", html)          # les 4 pages du document
        self.assertNotIn("jours de validité", html)   # pastille CTA omise
        self.assertNotIn("30 jours", html)      # aucun repli forfaitaire

    def test_validite_du_devis_est_imprimee(self):
        html = self._html()                     # sample_data → 30 jours réels
        self.assertIn("30 jours", html)
        self.assertIn("jours de validité", html)

    def test_validite_repli_sur_la_date_dexpiration(self):
        """Sans nombre de jours mais avec une date d'échéance, la ligne des
        conditions publie la date — jamais un « None »."""
        data = sample_data.build("agrumes")
        data.pop("validity_days", None)
        data["valid_until"] = "31/12/2026"
        html = render.build_html(renderer._augment(data))
        self.assertIn("31/12/2026", html)
        self.assertNotIn("None", html)


class TestInstallationPhotoSelector(SimpleTestCase):
    def test_nearest_kwc_same_mode_wins(self):
        from apps.ventes.quote_engine import installations as inst
        near = inst._score({"mode": "residentiel", "kwc": 5}, 6, "residentiel")
        far = inst._score({"mode": "residentiel", "kwc": 15}, 6, "residentiel")
        self.assertLess(near, far)

    def test_agricole_prefers_real_photo_over_universal(self):
        from apps.ventes.quote_engine import installations as inst
        resid = inst._score({"mode": "residentiel", "kwc": 6}, 6, "agricole")
        univ = inst._score({"mode": None, "kwc": None}, 6, "agricole")
        self.assertLess(resid, univ)

    def test_seed_photo_available(self):
        from apps.ventes.quote_engine import installations as inst
        self.assertTrue(inst.pick_b64(7.1, "agricole"))   # default.jpg seed

    def test_cover_embeds_hero_photo(self):
        html = render.build_html(renderer._augment(sample_data.build("agrumes")))
        self.assertIn("data:image/jpeg;base64,", html)    # installation photo hero


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
