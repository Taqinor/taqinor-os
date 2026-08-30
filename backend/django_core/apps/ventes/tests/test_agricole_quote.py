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
        # QJR151(b) — la quantité évitée est dérivée de la facture actuelle
        # (ici modélisée sur le volume d'eau réel), plus du CV de la pompe neuve.
        self.assertIn("gasoil", eco["fuel_qty_label"])
        litres = round(eco["annual_fuel_now"] / 13.5)
        self.assertIn(f"{litres:,}".replace(",", " "), eco["fuel_qty_label"])

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

    # ── QJR152(a) — un seul moteur agronomique ───────────────────────────────
    def test_besoin_de_pointe_est_le_max_de_la_serie_mensuelle(self):
        """Le nombre imprimé en page 2 EST la plus haute barre de son graphe."""
        from apps.ventes.quote_engine.agricole import agronomy
        for key in sample_data.keys():
            data = renderer._augment(sample_data.build(key))
            mensuel = data["monthly_need_m3day"]
            self.assertTrue(mensuel, key)
            self.assertEqual(data["besoin_m3j"], round(max(mensuel)), key)
        self.assertFalse(hasattr(agronomy, "water_demand_from_farm"))
        self.assertFalse(hasattr(agronomy, "KC_MID"))
        self.assertFalse(hasattr(agronomy, "ET0_PEAK_MM_J"))

    def test_besoin_explicite_du_client_reste_prioritaire(self):
        data = sample_data.build("agrumes")
        data["etude"]["besoin_m3j"] = 64
        self.assertEqual(economics.compute(data)["besoin_m3j"], 64)

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
        """Les bonbonnes/CO₂ évités viennent de la consommation ACTUELLE du
        client (dépense saisie, sinon coût modélisé sur son volume d'eau réel),
        jamais du CV de la pompe solaire NEUVE."""
        data = sample_data.build("agrumes")
        data["etude"]["fuel_spend_current"] = 40000
        eco = economics.compute(data)
        # 40 000 MAD / 50 MAD la bonbonne = 800 bonbonnes — une DÉRIVATION de la
        # dépense saisie, jamais un modèle sur le CV de la pompe neuve.
        self.assertIn("800 bonbonnes", eco["fuel_qty_label"])
        self.assertGreater(eco["co2_t"], 0)

    def test_impact_omis_sans_aucune_donnee_de_consommation(self):
        """Pompe sans courbe (aucun m³/jour) et aucune dépense saisie : le
        bandeau publiait quand même un décompte de bonbonnes."""
        data = sample_data.build("agrumes")
        data["etude"]["m3_jour"] = None
        eco = economics.compute(data)
        self.assertFalse(eco["has_water"])
        self.assertEqual(eco["annual_fuel_now"], 0)
        self.assertEqual(eco["co2_t"], 0)
        self.assertEqual(eco["fuel_qty_label"], "")

    def test_impact_omis_sans_energie_actuelle(self):
        data = sample_data.build("agrumes")
        data["etude"]["current_fuel"] = "none"
        eco = economics.compute(data)
        self.assertEqual(eco["co2_t"], 0)
        self.assertEqual(eco["fuel_qty_label"], "")

    def test_impact_ne_depend_plus_du_cv_de_la_pompe_neuve(self):
        data = sample_data.build("agrumes")
        base = economics.compute(data)
        self.assertGreater(base["co2_t"], 0)
        data["etude"]["pompe_cv"] = "15"          # pompe deux fois plus grosse
        self.assertEqual(economics.compute(data)["co2_t"], base["co2_t"])
        self.assertEqual(economics.compute(data)["fuel_qty_label"],
                         base["fuel_qty_label"])

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

    # ── QJR152(b) — la promesse de suffisance n'est servie que si elle est vraie
    def test_page2_ne_publie_quun_seul_besoin_de_pointe(self):
        """Le nombre du texte et la plus haute barre du graphe concordent."""
        for key in sample_data.keys():
            data = renderer._augment(sample_data.build(key))
            html = render.build_html(data)
            besoin = data["besoin_m3j"]
            self.assertIn(f"{besoin} m³/jour", html, key)
            self.assertEqual(besoin, round(max(data["monthly_need_m3day"])), key)

    def test_encadre_de_suffisance_seulement_si_le_besoin_est_couvert(self):
        data = sample_data.build("agrumes")
        data["etude"]["surface_ha"] = 6.0     # besoin de pointe > eau livrée
        html = render.build_html(renderer._augment(data))
        self.assertNotIn("sans manquer", html)
        self.assertNotIn("plus d'eau qu'il n'en faut", html)
        self.assertIn("Couverture partielle", html)

    def test_aucune_promesse_de_suffisance_sans_comparaison_calculable(self):
        data = sample_data.build("agrumes")
        data["etude"].pop("surface_ha", None)
        data["etude"].pop("crop", None)
        html = render.build_html(renderer._augment(data))
        self.assertNotIn("sans manquer", html)
        self.assertNotIn("Couverture partielle", html)
        self.assertIn("mois le plus exigeant", html)

    def test_abh_authorisation_guardrail_present(self):
        self.assertIn("ABH", self._html())

    # ── QJR153 — les garanties du PDF se dérivent du devis ───────────────────
    def test_badges_de_garantie_derives_des_lignes(self):
        from apps.ventes.quote_engine.agricole import theme as a_theme
        data = sample_data.build("agrumes")
        self.assertEqual(
            a_theme.garanties_du_devis(data),
            [("25", "ans", "Panneaux (perf.)"), ("5", "ans", "Variateur"),
             ("2", "ans", "Pompe")])
        html = render.build_html(renderer._augment(data))
        # la structure du devis ne porte AUCUNE garantie : plus de badge
        # « Structure 10 ans » promis sans donnée.
        self.assertNotIn('a3-bl">Structure<', html)
        self.assertIn('a3-bl">Pompe<', html)

    def test_badges_suivent_une_garantie_differente_du_forfait(self):
        data = sample_data.build("agrumes")
        for it in data["all_items"]:
            if "Panneau" in it["designation"]:
                it["garantie"] = "30 ans (perf.)"
            if "Structure" in it["designation"]:
                it["garantie"] = "10 ans"
        html = render.build_html(renderer._augment(data))
        self.assertIn('a3-bn">30<span>ans', html)     # badge page 3
        self.assertNotIn('a3-bn">25<span>', html)     # plus l'ancien forfait
        self.assertIn('a3-bl">Structure<', html)      # catégorie désormais garantie
        self.assertIn("Panneaux garantis <b>30 ans</b>", html)   # page 1

    def test_garantie_structuree_du_catalogue_prime_sur_le_texte(self):
        from apps.ventes.quote_engine.agricole import theme as a_theme
        data = sample_data.build("agrumes")
        for it in data["all_items"]:
            if "Pompe" in it["designation"]:
                it["garantie_mois"] = 36        # fiche produit : 3 ans
        self.assertIn(("3", "ans", "Pompe"), a_theme.garanties_du_devis(data))

    def test_aucune_duree_publiee_sans_garantie_au_devis(self):
        data = sample_data.build("agrumes")
        for it in data["all_items"]:
            it["garantie"] = ""
        html = render.build_html(renderer._augment(data))
        self.assertNotIn("Nos garanties", html)      # bloc entier omis
        self.assertNotIn('class="a3-badges"', html)
        self.assertNotIn('class="a3-bn"', html)      # aucun badge chiffré
        self.assertNotIn("Panneaux garantis", html)  # page 1
        # (« 3,5 ans » d'amortissement reste : ce n'est pas une garantie)
        for duree in ("25 ans", "10 ans", "2 ans"):
            self.assertNotIn(duree, html)

    def test_page4_degradee_derive_aussi_ses_garanties(self):
        data = sample_data.build("agrumes")
        data["etude"]["m3_jour"] = None          # branche « Zéro carburant »
        html = render.build_html(renderer._augment(data))
        self.assertNotIn("Panneaux 25 ans · structure 10 ans · variateur 5 ans",
                         html)
        self.assertIn("Panneaux (perf.) 25 ans", html)

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
        """Pompe sans courbe : aucun m³/jour, aucune dépense — aucun décompte."""
        data = sample_data.build("agrumes")
        data["etude"]["m3_jour"] = None
        self.assertNotIn("évitées/an", render.build_html(renderer._augment(data)))

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
