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
