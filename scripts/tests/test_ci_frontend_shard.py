"""Completeness guard for the Vitest lane split (WOW-CI4).

Same reasoning as scripts/tests/test_ci_shard.py: the lane lists decide WHICH
frontend tests CI runs. A file that fell out of the split would stop being tested
while `frontend-lint` stayed green — a gate that has quietly stopped gating. The
union is therefore asserted, not promised.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ci_frontend_shard as fs  # noqa: E402


class DiscoveryTests(unittest.TestCase):
    def test_discovery_matches_the_vitest_config_glob(self):
        """The script's glob and vitest.config.js must not drift apart.

        The config's default `include` is the source of truth for what the suite
        IS. If someone widens it (say to *.test.js) the script would silently keep
        shipping a narrower set, so pin the pattern here.
        """
        with open(fs.VITEST_CONFIG, encoding="utf-8") as fh:
            config = fh.read()
        self.assertIn(fs.INCLUDE_PATTERN, config)
        # And the config must still honour the lane variable, or every lane would
        # silently run the FULL suite (3x the work, and a green that means nothing).
        self.assertIn("VITEST_INCLUDE", config)

    def test_every_discovered_file_exists(self):
        for rel in fs.discover_files():
            self.assertTrue(os.path.isfile(os.path.join(fs.FRONTEND, rel)), rel)

    def test_discovery_finds_the_whole_suite(self):
        """Cross-check the walker against an independent glob."""
        import glob
        expected = {
            os.path.relpath(p, fs.FRONTEND).replace(os.sep, "/")
            for p in glob.glob(os.path.join(fs.FRONTEND, "src", "**", "*.test.jsx"),
                               recursive=True)
        }
        self.assertEqual(set(fs.discover_files()), expected)
        self.assertGreater(len(expected), 500, "suite anormalement petite")


class SplitCompletenessTests(unittest.TestCase):
    TOTALS = (1, 2, 3, 4, 6)

    def test_union_of_lanes_is_exactly_the_full_file_set(self):
        files = fs.discover_files()
        for total in self.TOTALS:
            with self.subTest(total=total):
                _f, _w, lanes = fs.plan(total)
                flat = [x for lane in lanes for x in lane]
                self.assertEqual(len(flat), len(set(flat)), "fichier dans DEUX lanes")
                self.assertEqual(set(flat), set(files),
                                 "l'union des lanes n'est pas la suite complete")
                self.assertEqual(len(lanes), total)

    def test_no_lane_is_empty(self):
        _f, _w, lanes = fs.plan(3)
        for i, lane in enumerate(lanes):
            self.assertTrue(lane, f"lane {i} vide")

    def test_cli_emits_a_comma_separated_list_matching_the_plan(self):
        """This exact string becomes VITEST_INCLUDE — its shape is load-bearing."""
        import contextlib
        import io as _io
        _f, _w, lanes = fs.plan(3)
        for i in range(3):
            buf = _io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = fs.main(["ci_frontend_shard.py", str(i), "3"])
            self.assertEqual(rc, 0)
            emitted = buf.getvalue().split(",")
            self.assertEqual(emitted, lanes[i])
            for path in emitted:
                self.assertNotIn(" ", path)
                self.assertTrue(path.startswith("src/"), path)

    def test_out_of_range_lane_is_refused(self):
        self.assertEqual(fs.main(["ci_frontend_shard.py", "3", "3"]), 2)
        self.assertEqual(fs.main(["ci_frontend_shard.py", "-1", "3"]), 2)


class BalanceTests(unittest.TestCase):
    def test_the_measured_table_is_wellformed(self):
        with open(fs.TIMINGS_PATH, encoding="utf-8") as fh:
            table = json.load(fh)
        self.assertTrue(table)
        for key, value in table.items():
            self.assertIsInstance(value, (int, float), key)
            # A 0.0 entry is FALSY and would be silently ignored by weigh(),
            # falling back to a per-case estimate. Same bug class the backend
            # table hit on 19/08.
            self.assertGreater(value, 0, key)
            self.assertTrue(key.endswith(".test.jsx"), key)

    def test_lanes_are_duration_balanced_not_file_count_balanced(self):
        """The regression this whole script exists to prevent.

        Vitest's own --shard produced 265/265/264 files running 381 s / 266 s /
        193 s — a 1.36x worst-to-ideal. Duration placement must do far better.
        """
        _f, weights, lanes = fs.plan(3)
        loads = [sum(weights[x] for x in lane) for lane in lanes]
        ideal = sum(weights.values()) / len(lanes)
        self.assertLess(max(loads) / ideal, 1.10,
                        f"lanes desequilibrees: {[round(x) for x in loads]}")

    def test_the_heaviest_files_are_spread_across_lanes(self):
        _f, weights, lanes = fs.plan(3)
        top = sorted(weights, key=lambda k: -weights[k])[:6]
        holders = {i for i, lane in enumerate(lanes) for x in lane if x in top}
        self.assertGreaterEqual(len(holders), 2,
                                "les fichiers les plus lourds sont concentres")


class TimingParserTests(unittest.TestCase):
    LINES = [
        "2026-08-19T01:56:00.0Z  ✓ src/pages/ui/UIShowcase.test.jsx (31 tests) 20163ms",
        "2026-08-19T01:56:01.0Z  ✓ src/lib/apps/useInstalledApps.test.jsx (22 tests) 30ms",
        "2026-08-19T01:56:02.0Z  ✓ src/x/Slow.test.jsx (2 tests) 1.5s",
        "2026-08-19T01:56:03.0Z not a result line at all",
    ]

    def test_ms_and_seconds_are_both_understood(self):
        got = fs.parse_log_durations(self.LINES)
        self.assertAlmostEqual(got["src/pages/ui/UIShowcase.test.jsx"], 20.163, places=3)
        self.assertAlmostEqual(got["src/lib/apps/useInstalledApps.test.jsx"], 0.03, places=3)
        self.assertAlmostEqual(got["src/x/Slow.test.jsx"], 1.5, places=3)

    def test_noise_is_ignored(self):
        self.assertEqual(fs.parse_log_durations(["", "random text"]), {})


if __name__ == "__main__":
    unittest.main()
