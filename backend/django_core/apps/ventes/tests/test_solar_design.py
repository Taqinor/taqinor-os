"""FG246 / FG247 / FG249 — tests des calculs d'ingénierie solaire.

Couvre :
* FG246 ``string_design`` — répartition MPPT, vérif Vmp/Voc à froid contre la
  fenêtre onduleur, ratio DC/AC, replis dégradés.
* FG247 ``match_inverter`` — appariement module/onduleur depuis un catalogue
  (mots-clés alignés sur builder.py), garde « jamais de produit sans prix ».
* FG249 ``optimize_orientation`` — balayage inclinaison/azimut via un stub PVGIS
  (aucun accès réseau dans les tests).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_solar_design -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.ventes import solar_design as sd


# ── FG246 : conception de chaînes & ratio DC/AC (calcul pur, SimpleTestCase) ───
class StringDesignTest(SimpleTestCase):
    def test_balanced_distribution_over_two_mppt(self):
        # 24 panneaux, fenêtre large : doit répartir en chaînes égales sur 2 MPPT.
        res = sd.string_design(
            24,
            module={"vmp": 34, "voc": 41, "puissance_w": 550},
            inverter={"v_min": 90, "v_max": 1000, "v_mppt_min": 120,
                      "v_mppt_max": 850, "n_mppt": 2, "ac_kw": 10},
        )
        self.assertTrue(res["ok"], res["warnings"])
        # chaînes × longueur = total
        self.assertEqual(
            res["strings"] * res["panels_per_string"], 24)
        # réparti également sur les 2 MPPT
        self.assertEqual(sum(res["string_layout"]), res["strings"])
        self.assertEqual(res["string_layout"][0], res["string_layout"][1])

    def test_voc_cold_under_vmax_flag(self):
        # Onduleur incompatible : même un SEUL module dépasse V_max au Voc froid
        # → le contrôle de sécurité échoue, warning « V_max », jamais d'exception.
        res = sd.string_design(
            5,
            module={"vmp": 40, "voc": 49, "puissance_w": 550,
                    "temp_coeff_voc": -0.30, "temp_coeff_vmp": -0.35},
            inverter={"v_min": 10, "v_max": 50, "v_mppt_min": 10,
                      "v_mppt_max": 45, "n_mppt": 1, "ac_kw": 4},
        )
        self.assertFalse(res["checks"]["voc_cold_under_vmax"])
        self.assertFalse(res["ok"])
        # Le Voc à froid (≈53.4 V pour 1 module) dépasse V_max (50 V).
        self.assertGreater(res["voltages"]["voc_cold"], 50)
        self.assertTrue(any("V_max" in w for w in res["warnings"]))

    def test_cold_voltage_higher_than_stc(self):
        # Vérifie la physique : Voc/Vmp montent quand il fait froid.
        res = sd.string_design(
            10,
            module={"vmp": 34, "voc": 41, "puissance_w": 450},
            inverter={"v_min": 90, "v_max": 1000, "v_mppt_min": 120,
                      "v_mppt_max": 900, "n_mppt": 2, "ac_kw": 5},
            cold_temp_c=-10, hot_temp_c=70,
        )
        self.assertGreater(res["voltages"]["voc_cold"],
                           res["voltages"]["vmp_stc"])
        self.assertGreater(res["voltages"]["vmp_cold"],
                           res["voltages"]["vmp_hot"])

    def test_dc_ac_ratio(self):
        # 18 × 550 W = 9.9 kWc DC ; onduleur 7 kW → ratio ≈ 1.414.
        res = sd.string_design(
            18,
            module={"vmp": 34, "voc": 41, "puissance_w": 550},
            inverter={"v_min": 90, "v_max": 1000, "v_mppt_min": 120,
                      "v_mppt_max": 900, "n_mppt": 2, "ac_kw": 7},
        )
        self.assertAlmostEqual(res["dc_kw"], 9.9, places=2)
        self.assertAlmostEqual(res["dc_ac_ratio"], round(9.9 / 7, 3), places=3)
        # ratio > 1.5 ? non ici, mais le champ existe toujours.
        self.assertIsNotNone(res["dc_ac_ratio"])

    def test_high_dc_ac_ratio_warns(self):
        res = sd.string_design(
            30,
            module={"vmp": 34, "voc": 41, "puissance_w": 550},
            inverter={"v_min": 90, "v_max": 1100, "v_mppt_min": 120,
                      "v_mppt_max": 1000, "n_mppt": 2, "ac_kw": 8},
        )
        # 30 × 550 = 16.5 kWc / 8 kW = 2.06 → warning « élevé ».
        self.assertGreater(res["dc_ac_ratio"], 1.5)
        self.assertTrue(any("DC/AC" in w for w in res["warnings"]))

    def test_no_ac_kw_means_no_ratio(self):
        res = sd.string_design(
            12,
            module={"vmp": 34, "voc": 41, "puissance_w": 450},
            inverter={"v_min": 90, "v_max": 1000, "v_mppt_min": 120,
                      "v_mppt_max": 900, "n_mppt": 2},  # pas d'ac_kw
        )
        self.assertIsNone(res["dc_ac_ratio"])

    def test_zero_panels_safe(self):
        res = sd.string_design(0)
        self.assertEqual(res["n_panels"], 0)
        self.assertEqual(res["strings"], 0)
        self.assertFalse(res["ok"])
        self.assertEqual(res["dc_ac_ratio"], None)

    def test_defaults_apply_when_no_specs(self):
        # Sans module/onduleur fournis, les défauts sensés s'appliquent.
        res = sd.string_design(12)
        self.assertEqual(res["n_mppt"], sd.DEFAULT_INVERTER_WINDOW["n_mppt"])
        self.assertGreater(res["dc_kw"], 0)
        self.assertIn("voc_cold", res["voltages"])

    def test_narrow_window_degrades_gracefully(self):
        # Fenêtre incohérente (min MPPT chaud > max MPPT froid) → not ok + warn,
        # mais jamais d'exception.
        res = sd.string_design(
            8,
            module={"vmp": 34, "voc": 41, "puissance_w": 450},
            inverter={"v_min": 700, "v_max": 750, "v_mppt_min": 700,
                      "v_mppt_max": 750, "n_mppt": 1, "ac_kw": 4},
        )
        self.assertFalse(res["ok"])
        self.assertTrue(res["warnings"])

    def test_non_integer_input_safe(self):
        # Une entrée non entière ne casse pas (repli à 0).
        res = sd.string_design("abc")
        self.assertEqual(res["n_panels"], 0)


# ── FG247 : appariement module–onduleur depuis le catalogue (DB) ──────────────
class MatchInverterTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from authentication.models import Company
        from apps.stock.models import Produit
        cls.company, _ = Company.objects.get_or_create(
            slug="fg247-co", defaults={"nom": "FG247 Co"})

        def mk(nom, prix, sku):
            return Produit.objects.create(
                company=cls.company, nom=nom, sku=sku,
                prix_vente=Decimal(str(prix)), quantite_stock=10)

        # Onduleurs réseau de tailles croissantes (mots-clés alignés builder.py).
        cls.r5 = mk("Onduleur réseau Huawei 5kW Monophasé", 14000, "ONDR5")
        cls.r10 = mk("Onduleur réseau Huawei 10kW Triphasé", 22000, "ONDR10")
        cls.r15 = mk("Onduleur réseau Huawei 15kW Triphasé", 30000, "ONDR15")
        # Un hybride.
        cls.h8 = mk("Onduleur hybride Deye 8kW Monophasé", 19000, "ONDH8")
        # Bruit : panneau / batterie ne doivent jamais être pris pour onduleurs.
        mk("Panneau Jinko 550W", 1100, "PAN550")
        mk("Batterie Deyness 5 kWh", 17000, "BAT5")
        # Onduleur réseau SANS prix → jamais candidat (garde auto-fill).
        Produit.objects.create(
            company=cls.company, nom="Onduleur réseau Sans Prix 6kW",
            sku="ONDRNOP", prix_vente=Decimal("0"), quantite_stock=1)

    def _produits(self):
        from apps.stock.models import Produit
        return list(Produit.objects.filter(company=self.company))

    def test_picks_smallest_compatible_reseau(self):
        # 16 × 550 W = 8.8 kWc DC ; ratio ≤ 1.35 → besoin ≥ 6.5 kW AC.
        # Le 5 kW (ratio 1.76) est rejeté, le 10 kW retenu.
        res = sd.match_inverter(
            self._produits(), n_panels=16, panel_w=550, hybrid=False)
        self.assertIsNotNone(res["inverter"])
        self.assertEqual(res["inverter"].id, self.r10.id)
        self.assertTrue(res["compatible"])
        self.assertEqual(res["ac_kw"], 10)

    def test_hybrid_family_selected(self):
        res = sd.match_inverter(
            self._produits(), n_panels=10, panel_w=550, hybrid=True)
        self.assertIsNotNone(res["inverter"])
        self.assertEqual(res["inverter"].id, self.h8.id)

    def test_never_picks_priceless_inverter(self):
        # Même si le « Sans Prix 6kW » conviendrait par la taille, il est exclu.
        res = sd.match_inverter(
            self._produits(), n_panels=12, panel_w=550, hybrid=False)
        self.assertIsNotNone(res["inverter"])
        self.assertNotEqual(res["inverter"].nom,
                            "Onduleur réseau Sans Prix 6kW")

    def test_no_candidate_returns_none(self):
        # Catalogue sans onduleur réseau chiffrable.
        from apps.stock.models import Produit
        empty = list(Produit.objects.filter(company=self.company, sku="PAN550"))
        res = sd.match_inverter(empty, n_panels=10, panel_w=550, hybrid=False)
        self.assertIsNone(res["inverter"])
        self.assertIn("aucun onduleur", res["reason"])

    def test_dc_kw_computed_from_panels(self):
        res = sd.match_inverter(
            self._produits(), n_panels=20, panel_w=600, hybrid=False)
        self.assertAlmostEqual(res["dc_kw"], 12.0, places=2)

    def test_classification_aligned_with_builder(self):
        # Garde-fou : les prédicats de ce module renvoient comme builder.py.
        from apps.ventes.quote_engine import builder as b
        for nom in ["Onduleur réseau Huawei 5kW", "Onduleur injection 6kW",
                    "Onduleur hybride Deye 8kW", "Batterie 5 kWh",
                    "Panneau 550W", "Câble solaire"]:
            self.assertEqual(sd.is_reseau_inverter(nom),
                             b._is_reseau_inverter(nom), nom)
            self.assertEqual(sd.is_hybrid_inverter(nom),
                             b._is_hybrid_inverter(nom), nom)
            self.assertEqual(sd.is_battery(nom), b._is_battery(nom), nom)
            self.assertEqual(sd.is_panel(nom), b._is_panel(nom), nom)


# ── FG249 : optimisation inclinaison/azimut (PVGIS stubbé, aucun réseau) ───────
class _FakeSettings:
    """Réglages minimaux pour optimize_orientation (pas de DB)."""
    inclinaison_defaut_deg = 30
    azimut_defaut_deg = 0
    productible_manuel_kwh_kwc = Decimal("1500.0")
    pvgis_actif = True


class OptimizeOrientationTest(SimpleTestCase):
    def _peak_fetch(self, best_tilt=30, best_az=0, base=1500.0, peak=1900.0):
        """Stub PVGIS : productible max au couple (best_tilt, best_az)."""
        def fetch(settings, lat, lon, peakpower_kwc=1.0, tilt=None,
                  azimuth=None, loss=14):
            # Pénalité simple : éloignement de l'optimum réduit le productible.
            d = abs((tilt or 0) - best_tilt) + abs((azimuth or 0) - best_az)
            val = max(base, peak - d * 2.0)
            return {
                "source": "pvgis",
                "productible_kwh_kwc": round(val, 1),
                "production_mensuelle_kwh_kwc": None,
                "reason": None,
            }
        return fetch

    def test_finds_optimum(self):
        s = _FakeSettings()
        res = sd.optimize_orientation(
            s, 33.5, -7.6,
            fetch=self._peak_fetch(best_tilt=30, best_az=0),
            tilt_range=(0, 60, 15), azimuth_range=(-90, 90, 30))
        self.assertIsNotNone(res["best"])
        self.assertEqual(res["best"]["tilt"], 30)
        self.assertEqual(res["best"]["azimuth"], 0)
        self.assertEqual(res["source"], "pvgis")
        self.assertGreater(res["evaluated"], 1)

    def test_gain_vs_default(self):
        # Optimum décalé du défaut société → gain positif rapporté.
        s = _FakeSettings()
        res = sd.optimize_orientation(
            s, 33.5, -7.6,
            fetch=self._peak_fetch(best_tilt=15, best_az=30),
            tilt_range=(0, 60, 15), azimuth_range=(-90, 90, 30))
        self.assertEqual(res["best"]["tilt"], 15)
        self.assertEqual(res["best"]["azimuth"], 30)
        self.assertIsNotNone(res["gain_vs_default_pct"])
        self.assertGreater(res["gain_vs_default_pct"], 0)
        self.assertEqual(res["default_orientation"]["tilt"], 30)

    def test_offline_manual_fallback(self):
        # Stub renvoyant TOUJOURS la même valeur manuelle (réseau bloqué).
        def manual_fetch(settings, lat, lon, peakpower_kwc=1.0, tilt=None,
                         azimuth=None, loss=14):
            return {
                "source": "manual",
                "productible_kwh_kwc": 1500.0,
                "production_mensuelle_kwh_kwc": None,
                "reason": "PVGIS indisponible (URLError)",
            }
        s = _FakeSettings()
        res = sd.optimize_orientation(
            s, 33.5, -7.6, fetch=manual_fetch,
            tilt_range=(0, 60, 30), azimuth_range=(-90, 90, 90))
        # Toutes égales → un « best » existe quand même, gain ≈ 0, source manual.
        self.assertEqual(res["source"], "manual")
        self.assertIsNotNone(res["best"])
        self.assertEqual(res["gain_vs_default_pct"], 0.0)

    def test_uses_real_pvgis_client_when_no_fetch(self):
        # Sans stub, la fonction importe le client PVGIS RÉEL
        # (apps.parametres.pvgis.fetch_productible). On le patche pour simuler
        # un repli manuel DÉTERMINISTE : selon l'environnement (sandbox/CI) le
        # réseau PVGIS peut être joignable ou non, donc on ne dépend jamais du
        # réseau — on prouve seulement que ce chemin (import du vrai client) est
        # bien emprunté quand aucun `fetch` n'est fourni.
        def manual_fetch(settings, lat, lon, peakpower_kwc=1.0, tilt=None,
                         azimuth=None, loss=14):
            return {
                "source": "manual",
                "productible_kwh_kwc": float(settings.productible_manuel_kwh_kwc),
                "production_mensuelle_kwh_kwc": None,
                "reason": "PVGIS indisponible (test)",
            }
        s = _FakeSettings()
        with patch("apps.parametres.pvgis.fetch_productible",
                   side_effect=manual_fetch):
            res = sd.optimize_orientation(
                s, 33.5, -7.6,
                tilt_range=(30, 30, 30), azimuth_range=(0, 0, 30))
        self.assertIsNotNone(res["best"])
        self.assertEqual(res["source"], "manual")
        self.assertEqual(res["best"]["productible_kwh_kwc"],
                         float(s.productible_manuel_kwh_kwc))

    def test_frange_inclusive(self):
        self.assertEqual(sd._frange(0, 60, 15), [0, 15, 30, 45, 60])
        self.assertEqual(sd._frange(-90, 90, 90), [-90, 0, 90])
        # borne non multiple : la dernière valeur force le stop exact.
        self.assertEqual(sd._frange(0, 50, 20), [0, 20, 40, 50])
        self.assertEqual(sd._frange(30, 30, 15), [30])


class ShadingAnalysisTest(SimpleTestCase):
    """FG250 — perte d'ombrage mensuelle depuis l'horizon + obstacles."""

    def test_no_shading_is_unity(self):
        res = sd.shading_analysis([], [])
        self.assertEqual(res["annual_loss_pct"], 0.0)
        self.assertEqual(res["production_factor"], 1.0)
        self.assertEqual(res["monthly_loss_pct"], [0.0] * 12)

    def test_south_obstacle_costs_more_than_north(self):
        south = sd.shading_analysis(
            [], [{"azimuth": 180, "elevation": 30}])
        north = sd.shading_analysis(
            [], [{"azimuth": 0, "elevation": 30}])
        self.assertGreater(south["annual_loss_pct"], north["annual_loss_pct"])
        # Un masque plein Nord (hémisphère N) ne coûte ~rien.
        self.assertLess(north["annual_loss_pct"], 1.0)

    def test_winter_loss_exceeds_summer(self):
        res = sd.shading_analysis(
            [], [{"azimuth": 180, "elevation": 25}])
        jan = res["monthly_loss_pct"][0]
        jun = res["monthly_loss_pct"][5]
        self.assertGreater(jan, jun)
        # Facteur de production mensuel = 1 - perte/100.
        self.assertAlmostEqual(
            res["monthly_production_factor"][0], 1 - jan / 100.0, places=3)

    def test_horizon_profile_drives_loss(self):
        flat = sd.shading_analysis(
            [{"azimuth": 180, "elevation": 2}], [])
        steep = sd.shading_analysis(
            [{"azimuth": 180, "elevation": 35}], [])
        self.assertGreater(steep["annual_loss_pct"], flat["annual_loss_pct"])

    def test_heavy_shading_warns(self):
        res = sd.shading_analysis(
            [], [{"azimuth": 180, "elevation": 45},
                 {"azimuth": 170, "elevation": 40}])
        self.assertTrue(res["warnings"])
        self.assertGreaterEqual(res["annual_loss_pct"], 20.0)

    def test_loss_is_bounded(self):
        res = sd.shading_analysis(
            [], [{"azimuth": 180, "elevation": 90}] * 10)
        for m in res["monthly_loss_pct"]:
            self.assertLessEqual(m, 90.0)
        self.assertLessEqual(res["horizon_severity"], 0.6)

    def test_malformed_input_safe(self):
        res = sd.shading_analysis(
            [{"azimuth": "x", "elevation": None}],
            [{"foo": "bar"}])
        self.assertEqual(res["annual_loss_pct"], 0.0)


class GenerateBoqTest(SimpleTestCase):
    """FG251 — nomenclature électrique (BOQ) déduite du design."""

    def test_zero_panels_empty(self):
        res = sd.generate_boq(n_panels=0)
        self.assertEqual(res["items"], [])
        self.assertTrue(res["warnings"])

    def test_basic_reseau_boq_categories(self):
        sr = sd.string_design(
            12, inverter={"ac_kw": 5, "n_mppt": 2})
        res = sd.generate_boq(
            n_panels=12, string_result=sr, installation_type="reseau")
        cats = {it["categorie"] for it in res["items"]}
        for expected in ("Câblage DC", "Câblage AC", "Protection DC",
                         "Protection AC", "Coffret", "Mise à la terre",
                         "Structure"):
            self.assertIn(expected, cats)
        # Pas de batterie sur du réseau pur.
        self.assertNotIn("Batterie", cats)
        # Jamais de prix dans une ligne de BOQ.
        for it in res["items"]:
            self.assertNotIn("prix", it)
            self.assertNotIn("prix_achat", it)

    def test_structure_scales_with_panels(self):
        small = sd.generate_boq(n_panels=6)
        big = sd.generate_boq(n_panels=24)

        def rails(boq):
            return next(it["quantite"] for it in boq["items"]
                        if it["designation"].startswith("Rail"))
        self.assertGreater(rails(big), rails(small))

    def test_three_phase_breaker_and_cable(self):
        mono = sd.generate_boq(n_panels=20, kwc=11, phases=1)
        tri = sd.generate_boq(n_panels=20, kwc=11, phases=3)
        self.assertEqual(mono["summary"]["phases"], 1)
        self.assertEqual(tri["summary"]["phases"], 3)
        # Le triphasé tire moins de courant → calibre plus petit.
        self.assertLessEqual(tri["summary"]["ac_breaker_amp"],
                             mono["summary"]["ac_breaker_amp"])

    def test_battery_adds_lines(self):
        res = sd.generate_boq(
            n_panels=10, has_battery=True, installation_type="hybride")
        cats = {it["categorie"] for it in res["items"]}
        self.assertIn("Batterie", cats)
        self.assertIn("Protection batterie", cats)

    def test_strings_drive_string_protections(self):
        sr = sd.string_design(
            16, inverter={"ac_kw": 6, "n_mppt": 2})
        res = sd.generate_boq(n_panels=16, string_result=sr)
        fuses = next(it["quantite"] for it in res["items"]
                     if it["designation"].startswith("Sectionneur-fusible"))
        self.assertEqual(fuses, sr["strings"])


# ── FG255 : dimensionnement borne VE & impact autoconsommation ───────────────
class EvChargerSizingTest(SimpleTestCase):
    def test_mono_vs_tri_current_and_breaker(self):
        # Même puissance, le triphasé tire ~√3 moins de courant → calibre <=.
        mono = sd.ev_charger_sizing(borne_kw=7.4, phases=1)
        tri = sd.ev_charger_sizing(borne_kw=7.4, phases=3)
        self.assertEqual(mono["borne"]["phases"], 1)
        self.assertEqual(tri["borne"]["phases"], 3)
        self.assertEqual(mono["borne"]["voltage_v"], 230.0)
        self.assertEqual(tri["borne"]["voltage_v"], 400.0)
        self.assertGreater(mono["borne"]["line_current_a"],
                           tri["borne"]["line_current_a"])
        self.assertLessEqual(tri["borne"]["breaker_a"],
                             mono["borne"]["breaker_a"])
        # 7.4 kW mono à 230 V ≈ 32 A nominal → calibre 40 A (1.25×).
        self.assertAlmostEqual(mono["borne"]["line_current_a"], 32.2, delta=0.5)
        self.assertEqual(mono["borne"]["breaker_a"], 50)

    def test_daily_demand_from_km_and_sessions(self):
        # 18 kWh/100km × 40 km = 7.2 kWh/session ; 2 sessions ; rendement 0.9.
        res = sd.ev_charger_sizing(
            borne_kw=11, phases=3, sessions_per_day=2,
            kwh_per_100km=18.0, km_per_session=40.0)
        self.assertAlmostEqual(res["energy"]["per_session_kwh"], 7.2, places=2)
        # 7.2 × 2 / 0.9 = 16.0 kWh prélevés au tableau.
        self.assertAlmostEqual(res["energy"]["daily_demand_kwh"], 16.0,
                               places=2)
        self.assertEqual(res["energy"]["sessions_per_day"], 2.0)

    def test_explicit_energy_per_session_overrides_km(self):
        res = sd.ev_charger_sizing(
            borne_kw=7.4, phases=1, sessions_per_day=1,
            energy_per_session_kwh=10.0, km_per_session=999)
        self.assertEqual(res["energy"]["per_session_kwh"], 10.0)
        # 10 / 0.9 ≈ 11.11 kWh.
        self.assertAlmostEqual(res["energy"]["daily_demand_kwh"], 11.11,
                               places=2)

    def test_pv_surplus_lifts_self_consumption(self):
        # 30 kWh produits, 12 autoconsommés → 18 de surplus. VE demande 16 kWh.
        res = sd.ev_charger_sizing(
            borne_kw=11, phases=3, sessions_per_day=2,
            kwh_per_100km=18.0, km_per_session=40.0,
            pv_daily_production_kwh=30.0, pv_self_consumption_kwh=12.0)
        pv = res["pv_impact"]
        self.assertEqual(pv["available_surplus_kwh"], 18.0)
        # Le VE (16 kWh) est entièrement couvert par le surplus (18 kWh).
        self.assertEqual(pv["solar_covered_kwh"], 16.0)
        self.assertEqual(pv["grid_kwh"], 0.0)
        self.assertEqual(pv["solar_coverage_pct"], 100.0)
        # Base 12/30 = 40 % ; nouveau (12+16)/30 = 93.3 % ; gain ≈ 53.3 pts.
        self.assertEqual(pv["base_self_consumption_pct"], 40.0)
        self.assertEqual(pv["new_self_consumption_pct"], 93.3)
        self.assertAlmostEqual(pv["self_consumption_gain_pts"], 53.3, places=1)

    def test_surplus_capped_partial_coverage_warns(self):
        # Surplus 5 kWh < demande VE → couverture partielle + import réseau.
        res = sd.ev_charger_sizing(
            borne_kw=7.4, phases=1, sessions_per_day=1,
            energy_per_session_kwh=18.0,
            pv_daily_production_kwh=20.0, pv_surplus_kwh=5.0)
        pv = res["pv_impact"]
        self.assertEqual(pv["solar_covered_kwh"], 5.0)
        self.assertGreater(pv["grid_kwh"], 0.0)
        self.assertLess(pv["solar_coverage_pct"], 50.0)
        self.assertTrue(any("moins de la moitié" in w
                            for w in res["warnings"]))

    def test_pv_surplus_from_kwc(self):
        # Sans production fournie, déduite de kWc × productible / 365.
        res = sd.ev_charger_sizing(
            borne_kw=7.4, pv_kwc=5.0, pv_surplus_kwh=10.0,
            energy_per_session_kwh=8.0)
        prod = res["pv_impact"]["pv_daily_production_kwh"]
        # 5 kWc × 1700 / 365 ≈ 23.3 kWh/jour.
        self.assertAlmostEqual(prod, 23.29, places=1)

    def test_charge_window_fit_flag(self):
        # 8 kWh / 0.9 / 3.7 kW ≈ 2.4 h — tient dans 4 h, pas dans 2 h.
        ok = sd.ev_charger_sizing(
            borne_kw=3.7, energy_per_session_kwh=8.0, charge_window_h=4.0)
        ko = sd.ev_charger_sizing(
            borne_kw=3.7, energy_per_session_kwh=8.0, charge_window_h=2.0)
        self.assertTrue(ok["borne"]["fits_window"])
        self.assertFalse(ko["borne"]["fits_window"])
        self.assertTrue(any("fenêtre" in w for w in ko["warnings"]))

    def test_recommended_standard_power(self):
        # 6 kW saisis → borne standard recommandée 7.4 kW.
        res = sd.ev_charger_sizing(borne_kw=6.0)
        self.assertEqual(res["borne"]["recommended_kw"], 7.4)

    def test_degraded_inputs_never_raise(self):
        # Entrées absurdes/None : bornées, jamais d'exception.
        res = sd.ev_charger_sizing(
            borne_kw=0, phases=0, sessions_per_day=-3,
            energy_per_session_kwh=None, kwh_per_100km=None,
            km_per_session=None, pv_kwc=-5, pv_surplus_kwh=-1)
        self.assertGreater(res["borne"]["kw"], 0)
        self.assertEqual(res["borne"]["phases"], 1)
        self.assertGreaterEqual(res["energy"]["daily_demand_kwh"], 0.0)
        # Pas de contexte PV exploitable → impact non chiffré, pas de crash.
        self.assertIsNone(res["pv_impact"]["solar_covered_kwh"])


# ── FG256 : stockage & dispatch batterie (backup) (calcul pur, SimpleTestCase) ─
class BatteryStorageSizingTest(SimpleTestCase):
    def test_autoconso_stores_surplus_capped_by_night_load(self):
        # 30 kWh produits, 12 autoconsommés → 18 de surplus ; besoin nuit 14.
        res = sd.battery_storage_sizing(
            mode="autoconso", pv_daily_production_kwh=30.0,
            pv_self_consumption_kwh=12.0, night_load_kwh=14.0)
        ac = res["autoconso"]
        self.assertEqual(ac["daily_surplus_kwh"], 18.0)
        # On ne stocke que ce qui sera redéchargé la nuit → 14 kWh utiles.
        self.assertEqual(ac["usable_kwh"], 14.0)
        # 18 − 14 = 4 kWh de surplus non stocké.
        self.assertEqual(ac["spilled_surplus_kwh"], 4.0)
        self.assertEqual(res["binding_objective"], "autoconso")
        self.assertTrue(any("ne sera pas stockée" in w
                            for w in res["warnings"]))

    def test_autoconso_night_load_caps_below_surplus(self):
        # Besoin nuit (8) < surplus (18) → utile = 8, pas le surplus entier.
        res = sd.battery_storage_sizing(
            mode="autoconso", daily_surplus_kwh=18.0, night_load_kwh=8.0)
        self.assertEqual(res["autoconso"]["usable_kwh"], 8.0)
        self.assertEqual(res["autoconso"]["spilled_surplus_kwh"], 10.0)

    def test_autoconso_surplus_from_kwc(self):
        # Sans production fournie, déduite de kWc × productible / 365.
        res = sd.battery_storage_sizing(
            mode="autoconso", pv_kwc=6.0, pv_self_consumption_kwh=10.0,
            night_load_kwh=100.0)
        prod = res["autoconso"]["pv_daily_production_kwh"]
        # 6 kWc × 1700 / 365 ≈ 27.95 kWh/jour.
        self.assertAlmostEqual(prod, 27.95, places=1)
        # Surplus = prod − 10 ; besoin nuit 100 ne plafonne pas → tout le surplus.
        self.assertAlmostEqual(
            res["autoconso"]["usable_kwh"], prod - 10.0, places=1)

    def test_backup_capacity_is_load_times_hours(self):
        # 2 kW critiques × 8 h = 16 kWh utiles ; puissance 2 × 1.25 = 2.5 kW.
        res = sd.battery_storage_sizing(
            mode="backup", critical_load_kw=2.0, backup_hours=8.0)
        bk = res["backup"]
        self.assertEqual(bk["usable_kwh"], 16.0)
        self.assertEqual(bk["usable_kw"], 2.5)
        self.assertEqual(res["binding_objective"], "backup")

    def test_usable_to_nominal_uses_dod_and_round_trip(self):
        # DoD 0.5, rendement 1.0 → nominal = utile / 0.5 = 2× l'utile.
        res = sd.battery_storage_sizing(
            mode="backup", critical_load_kw=1.0, backup_hours=5.0,
            depth_of_discharge=0.5, round_trip_efficiency=1.0)
        self.assertEqual(res["backup"]["usable_kwh"], 5.0)
        self.assertAlmostEqual(res["backup"]["nominal_kwh"], 10.0, places=2)

    def test_round_trip_efficiency_inflates_nominal(self):
        # DoD 1.0, rendement 0.81 → nominal = utile / √0.81 = utile / 0.9.
        res = sd.battery_storage_sizing(
            mode="backup", critical_load_kw=1.0, backup_hours=9.0,
            depth_of_discharge=1.0, round_trip_efficiency=0.81)
        # 9 / 0.9 = 10.0 kWh nominaux.
        self.assertAlmostEqual(res["backup"]["nominal_kwh"], 10.0, places=2)

    def test_both_modes_pick_largest_as_binding(self):
        # Autoconso 14 kWh vs backup 24 kWh → backup dimensionne.
        res = sd.battery_storage_sizing(
            mode="both", pv_daily_production_kwh=30.0,
            pv_self_consumption_kwh=12.0, night_load_kwh=14.0,
            critical_load_kw=3.0, backup_hours=8.0)
        self.assertEqual(res["autoconso"]["usable_kwh"], 14.0)
        self.assertEqual(res["backup"]["usable_kwh"], 24.0)
        self.assertEqual(res["binding_objective"], "backup")
        # La capacité retenue est la plus grande des deux.
        self.assertEqual(res["recommended"]["usable_kwh"], 24.0)
        # La puissance retenue est le max des deux pics (backup 3×1.25=3.75).
        self.assertEqual(res["recommended"]["usable_kw"], 3.75)

    def test_recommended_current_from_voltage(self):
        # Pic 2.5 kW à 48 V → courant ≈ 52.1 A.
        res = sd.battery_storage_sizing(
            mode="backup", critical_load_kw=2.0, backup_hours=4.0,
            system_voltage_v=48.0)
        self.assertAlmostEqual(
            res["recommended"]["current_a"], 52.1, delta=0.5)

    def test_dod_and_efficiency_clamped_to_one(self):
        # DoD/rendement absurdes (>1) plafonnés à 1, sans crash.
        res = sd.battery_storage_sizing(
            mode="backup", critical_load_kw=1.0, backup_hours=4.0,
            depth_of_discharge=1.5, round_trip_efficiency=2.0)
        self.assertEqual(res["depth_of_discharge"], 1.0)
        self.assertEqual(res["round_trip_efficiency"], 1.0)
        # DoD 1 & rendement 1 → nominal == utile.
        self.assertEqual(
            res["backup"]["nominal_kwh"], res["backup"]["usable_kwh"])
        self.assertTrue(any("plafonné" in w for w in res["warnings"]))

    def test_missing_autoconso_context_warns_not_raises(self):
        # Pas de surplus exploitable → autoconso non chiffré, pas d'exception.
        res = sd.battery_storage_sizing(mode="autoconso")
        self.assertIsNone(res["autoconso"]["usable_kwh"])
        self.assertIsNone(res["binding_objective"])
        self.assertTrue(any("surplus" in w for w in res["warnings"]))

    def test_missing_backup_context_warns_not_raises(self):
        # Charge critique / heures manquantes → backup non chiffré, pas de crash.
        res = sd.battery_storage_sizing(mode="backup", critical_load_kw=2.0)
        self.assertIsNone(res["backup"]["usable_kwh"])
        self.assertIsNone(res["binding_objective"])
        self.assertTrue(any("backup" in w for w in res["warnings"]))

    def test_degraded_inputs_never_raise(self):
        # Entrées absurdes/None : bornées, jamais d'exception.
        res = sd.battery_storage_sizing(
            mode="both", pv_daily_production_kwh=-5,
            pv_self_consumption_kwh=None, daily_surplus_kwh=-10,
            critical_load_kw=-2, backup_hours=-4,
            depth_of_discharge=0, round_trip_efficiency=-1,
            system_voltage_v=0)
        # DoD/rendement/tension absurdes → bornés à leurs défauts > 0.
        self.assertGreater(res["depth_of_discharge"], 0)
        self.assertGreater(res["round_trip_efficiency"], 0)
        self.assertGreater(res["system_voltage_v"], 0)
        # Aucun objectif chiffrable → recommandation vide, pas d'exception.
        self.assertIsNone(res["binding_objective"])
        self.assertIsNone(res["recommended"]["usable_kwh"])

    def test_unknown_mode_falls_back_to_autoconso(self):
        res = sd.battery_storage_sizing(
            mode="banane", daily_surplus_kwh=10.0, night_load_kwh=10.0)
        self.assertIsNotNone(res["autoconso"])
        self.assertIsNone(res["backup"])
        self.assertEqual(res["autoconso"]["usable_kwh"], 10.0)
        self.assertTrue(any("inconnu" in w for w in res["warnings"]))
