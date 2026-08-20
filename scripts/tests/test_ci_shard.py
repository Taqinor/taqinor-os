"""Completeness + determinism guard for the CI backend-test sharding.

WHY THIS TEST IS THE POINT OF THE WHOLE MECHANISM. The shards decide WHICH
tests CI runs. If a module ever fell out of the split — a discovery pattern
that stops matching `tests_x.py`, an off-by-one in the assignment, a lane list
that silently truncates — the affected tests would stop running while every
required check stayed GREEN. That is strictly worse than a red build: it is a
gate that has quietly stopped gating. Balance is an optimisation and may drift;
completeness may not, so it is asserted here rather than promised in a comment.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ci_shard  # noqa: E402

REPO_ROOT = ci_shard.REPO_ROOT
DJANGO_ROOT = os.path.join(REPO_ROOT, "backend", "django_core")


class DiscoveryTests(unittest.TestCase):
    def test_units_match_djangos_own_discovery_pattern(self):
        """Every `test*.py` on disk is a unit, and every unit exists on disk.

        Django's default discovery pattern is `test*.py` at any depth. This
        asserts the sharder's view is exactly that set — no more (a label for a
        file that does not exist fails the run) and no less (a file nobody runs).
        """
        expected = set()
        for root in [os.path.join(DJANGO_ROOT, "apps", d)
                     for d in sorted(os.listdir(os.path.join(DJANGO_ROOT, "apps")))
                     if os.path.isdir(os.path.join(DJANGO_ROOT, "apps", d))
                     and os.path.exists(
                         os.path.join(DJANGO_ROOT, "apps", d, "__init__.py"))
                     ] + [os.path.join(DJANGO_ROOT, t) for t in ci_shard.TOP_LEVEL]:
            if not os.path.isdir(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in ci_shard.SKIP_DIRS]
                for name in filenames:
                    if name.startswith("test") and name.endswith(".py"):
                        rel = os.path.relpath(os.path.join(dirpath, name),
                                              DJANGO_ROOT)
                        expected.add(rel.replace(os.sep, "/")[:-3].replace("/", "."))
        self.assertEqual(set(ci_shard.discover_units()), expected)

    def test_every_unit_is_an_importable_dotted_path(self):
        """A dotted label only works if every directory on the way is a package."""
        for unit in ci_shard.discover_units():
            parts = unit.split(".")
            path = DJANGO_ROOT
            for segment in parts[:-1]:
                path = os.path.join(path, segment)
                self.assertTrue(
                    os.path.exists(os.path.join(path, "__init__.py")),
                    f"{unit}: {path} n'est pas un paquet — Django ne pourra pas "
                    "importer ce label, le module ne serait jamais teste.",
                )
            self.assertTrue(os.path.isfile(path + os.sep + parts[-1] + ".py")
                            or os.path.isfile(os.path.join(path, parts[-1] + ".py")))

    def test_the_known_awkward_files_are_covered(self):
        """The two shapes a naive glob would miss, pinned explicitly."""
        units = set(ci_shard.discover_units())
        # a `tests_*.py` (plural) inside the tests package
        self.assertIn("apps.ventes.tests.tests_ntux13_dupliquer_devis", units)
        # a test file sitting at APP level, outside the tests package
        self.assertIn("apps.ventes.tests_qj9_attribution_capi", units)


class SplitCompletenessTests(unittest.TestCase):
    TOTALS = (1, 2, 3, 4, 6, 8, 10, 12, 16)

    def test_union_of_lanes_is_exactly_the_full_unit_set(self):
        units = ci_shard.discover_units()
        for total in self.TOTALS:
            with self.subTest(total=total):
                _u, _w, lanes = ci_shard.plan(total)
                flat = [unit for lane in lanes for unit in lane]
                self.assertEqual(len(flat), len(set(flat)),
                                 "un module est assigne a DEUX lanes")
                self.assertEqual(set(flat), set(units),
                                 "l'union des lanes n'est pas la suite complete")
                self.assertEqual(len(lanes), total)

    def test_no_lane_is_empty(self):
        """An empty lane means a wasted runner and, usually, a sizing mistake."""
        _u, _w, lanes = ci_shard.plan(8)
        for i, lane in enumerate(lanes):
            self.assertTrue(lane, f"lane {i} est vide")

    def test_assignment_is_deterministic(self):
        """Two calls must agree — CI reruns a single lane by index, not by luck."""
        first = ci_shard.plan(8)[2]
        second = ci_shard.plan(8)[2]
        self.assertEqual(first, second)

    def test_cli_shard_output_matches_the_plan(self):
        """`ci_shard.py i n` prints exactly lane i of the n-lane plan."""
        import io
        import contextlib
        _u, _w, lanes = ci_shard.plan(4)
        for i in range(4):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ci_shard.main(["ci_shard.py", str(i), "4"])
            self.assertEqual(rc, 0)
            self.assertEqual(buf.getvalue().split(), lanes[i])

    def test_out_of_range_shard_is_refused(self):
        self.assertEqual(ci_shard.main(["ci_shard.py", "4", "4"]), 2)
        self.assertEqual(ci_shard.main(["ci_shard.py", "-1", "4"]), 2)


class BalanceTests(unittest.TestCase):
    def test_the_measured_table_is_wellformed(self):
        with open(ci_shard.TIMINGS_PATH, encoding="utf-8") as fh:
            table = json.load(fh)
        self.assertTrue(table, "table de chronometrage vide")
        for key, value in table.items():
            self.assertIsInstance(value, (int, float), key)
            self.assertGreater(value, 0, key)

    def test_balance_is_far_better_than_the_naive_round_robin(self):
        """The regression this rewrite exists to prevent.

        On the 18/08 run the round-robin put apps.crm AND apps.ventes on one
        lane: that lane carried 767 s while the lightest carried 83 s — 9.2x.

        VOLET F (20/08) — LA REFERENCE N'EST PLUS LA MOYENNE, C'EST LE PLANCHER
        THEORIQUE. Comparer la pire lane a `total / lanes` supposait le travail
        infiniment divisible. Il ne l'est pas : une CLASSE de test est
        indivisible sous `--parallel`, et le depot en porte une de ~195 s
        (`test_gammes_offre.TestAcceptationGamme`) alors que la moyenne a 8
        lanes vaut ~106 s. Une lane a 1,85x de la moyenne etait donc signalee
        comme un desequilibre alors que c'etait le decoupage OPTIMAL — aucune
        assignation ne peut faire mieux tant que cette classe existe.
        `theoretical_floor` prend le plus grand des deux (moyenne, plus grosse
        classe) : c'est la seule borne qu'un planificateur puisse viser.
        """
        units, weights, lanes = ci_shard.plan(8)
        murs = [ci_shard.lane_makespan(lane, weights) for lane in lanes]
        sol = ci_shard.theoretical_floor(units, weights, 8)
        self.assertLess(max(murs) / sol, 1.5,
                        f"lanes desequilibrees: {[round(x) for x in murs]} "
                        f"(plancher {sol:.0f}s)")

    def test_the_binding_class_is_not_diluted_by_pro_rata(self):
        """Une classe MESUREE garde sa duree, elle n'est pas moyennee.

        Le defaut que le volet F a corrige : `test_gammes_offre` pesait 26 s au
        total pendant que sa classe `TestAcceptationGamme` en consommait 195 —
        repartir le poids du module au prorata du nombre de tests la rendait
        invisible, et le planificateur se declarait equilibre a 1,00x pendant
        que le shard 4 tournait trois fois plus longtemps que le shard 2.
        """
        mesures = dict(ci_shard.load_class_timings())
        if not mesures:
            self.skipTest("aucune table de classes mesuree")
        pire_nom = max(mesures, key=mesures.get)
        module = ci_shard.module_of_class(pire_nom)
        units = ci_shard.discover_units()
        if module not in units:
            self.skipTest(f"{module} n'est plus decouvert")
        weights = ci_shard.weigh(units, ci_shard.load_timings())
        blocs = ci_shard.class_weights(module, weights[module])
        self.assertAlmostEqual(
            max(blocs), mesures[pire_nom], places=1,
            msg=f"la classe {pire_nom} ({mesures[pire_nom]:.0f}s) doit garder "
                "sa duree mesuree, sinon le plancher d'une lane est sous-estime",
        )

    def test_heavy_apps_are_spread_not_pinned(self):
        """apps.ventes must not land on a single lane again."""
        _u, _w, lanes = ci_shard.plan(8)
        holders = sum(1 for lane in lanes
                      if any(u.startswith("apps.ventes.") for u in lane))
        self.assertGreaterEqual(holders, 4,
                                "apps.ventes est concentre sur trop peu de lanes")


class TimingParserTests(unittest.TestCase):
    """Le parser attribue un TROU a la rafale QUI LE SUIT, par CLASSE.

    La sortie `-v 2` est tamponnee : le runner horodate au moment du VIDAGE, pas
    de l'execution (mesure sur le run 32320058346 : 15 lignes consecutives a
    23 ms d'intervalle, et 0 % d'ecart entre deux lignes d'une meme classe). Un
    trou mesure donc le travail accompli JUSTE AVANT d'etre vide — celui de la
    ligne suivante. L'ancienne version l'imputait a la ligne PRECEDENTE, ce qui
    donnait systematiquement le cout d'une classe lente a sa voisine rapide.
    """

    LOG = [
        "2026-08-18T20:37:13.0000000Z test_a (apps.ventes.tests.test_pdf.C.test_a) ... ok",
        "2026-08-18T20:37:15.0000000Z test_b (apps.ventes.tests.test_pdf.C.test_b) ... ok",
        "2026-08-18T20:37:20.0000000Z test_c (apps.crm.tests.test_lead.D.test_c) ... ok",
        "2026-08-18T20:37:21.0000000Z Ran 3 tests in 8.000s",
    ]

    def test_a_gap_is_charged_to_the_burst_that_follows_it(self):
        got = ci_shard.parse_log_durations(self.LOG)
        # 13->15 : 2 s de travail rendus par la 2e ligne, meme classe C
        self.assertAlmostEqual(got["apps.ventes.tests.test_pdf.C"], 2.0, places=3)
        # 15->20 : 5 s attribuees a la classe SUIVANTE (D), pas a C
        self.assertAlmostEqual(got["apps.crm.tests.test_lead.D"], 5.0, places=3)

    def test_durations_are_keyed_by_class_not_module(self):
        """La CLASSE est l'unite indivisible sous --parallel : c'est elle qu'on
        mesure. Le poids du module en decoule par somme."""
        got = ci_shard.parse_log_durations(self.LOG)
        self.assertNotIn("apps.ventes.tests.test_pdf", got)
        self.assertEqual(
            ci_shard.module_of_class("apps.ventes.tests.test_pdf.C"),
            "apps.ventes.tests.test_pdf")

    def test_non_test_lines_are_ignored(self):
        self.assertEqual(ci_shard.parse_log_durations(["nothing here", ""]), {})


if __name__ == "__main__":
    unittest.main()
