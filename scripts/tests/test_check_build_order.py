"""Tests SCA5 — scripts/check_build_order.py.

Pure stdlib (unittest), no Django/DB needed. Run with:
    python -m unittest scripts.tests.test_check_build_order -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_build_order as cbo  # noqa: E402
import plan_lanes  # noqa: E402


VALID_FIXTURE = """\
waves:
  A:
    order: 1
    groups: [ARC-noyau, SCA-gov]
  A2:
    order: 2
    groups: [ARC-sweep]
  B:
    order: 3
    groups: [NTPLT, NTSEC]
  C:
    order: 4
    groups: [NTAPI]

aliases:
  ARC-noyau:
    prefix: ARC
    members: [1, 2, 6]
  ARC-sweep:
    prefix: ARC
    members: [3, 4, 5]
  SCA-gov:
    prefix: SCA
    members: [1, 2, 3]

edges:
  - group: ARC-sweep
    wave: A2
    after:
      ARC-noyau: 80
  - group: NTPLT
    wave: B
    after:
      ARC-noyau: 80
  - group: NTSEC
    wave: B
    after:
      ARC-noyau: 80
  - group: NTAPI
    wave: C
    after:
      NTPLT: 60
      NTSEC: 60

unmapped_ok:
  - DC
"""


def _write(text: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yml", delete=False, encoding="utf-8"
    )
    tmp.write(text)
    tmp.close()
    return Path(tmp.name)


class CheckAcyclicTests(unittest.TestCase):
    def test_valid_dag_has_no_failures(self):
        bo = plan_lanes._MiniYamlParser(VALID_FIXTURE).parse()
        self.assertEqual(cbo.check_acyclic(bo), [])

    def test_direct_two_node_cycle_is_caught(self):
        text = VALID_FIXTURE.replace(
            "  - group: NTAPI\n    wave: C\n    after:\n      NTPLT: 60\n      NTSEC: 60\n",
            "  - group: NTAPI\n    wave: C\n    after:\n      NTPLT: 60\n      NTSEC: 60\n"
            "  - group: NTPLT\n    wave: B\n    after:\n      NTAPI: 10\n",
        )
        bo = plan_lanes._MiniYamlParser(text).parse()
        failures = cbo.check_acyclic(bo)
        self.assertEqual(len(failures), 1)
        self.assertIn("cycle", failures[0])
        self.assertIn("NTPLT", failures[0])
        self.assertIn("NTAPI", failures[0])

    def test_self_loop_is_caught(self):
        # Insert the self-loop edge INSIDE the edges: block (appending after
        # unmapped_ok's own list would attach it to unmapped_ok instead).
        text = VALID_FIXTURE.replace(
            "\nunmapped_ok:",
            "  - group: NTAPI\n    wave: C\n    after:\n      NTAPI: 10\n\nunmapped_ok:",
        )
        bo = plan_lanes._MiniYamlParser(text).parse()
        failures = cbo.check_acyclic(bo)
        self.assertTrue(any("cycle" in f for f in failures))

    def test_sibling_aliases_sharing_a_real_prefix_are_not_a_false_cycle(self):
        """Regression: ARC-sweep depends on ARC-noyau, and both alias to the
        SAME real prefix (ARC) -- collapsing edge endpoints to their real
        prefix before cycle-checking would falsely report ARC -> ARC. The
        checker must operate at the authored (alias) granularity."""
        bo = plan_lanes._MiniYamlParser(VALID_FIXTURE).parse()
        failures = cbo.check_acyclic(bo)
        self.assertEqual(failures, [])


class CheckThresholdsTests(unittest.TestCase):
    def test_valid_thresholds_pass(self):
        bo = plan_lanes._MiniYamlParser(VALID_FIXTURE).parse()
        self.assertEqual(cbo.check_thresholds(bo), [])

    def test_non_numeric_threshold_is_caught(self):
        text = VALID_FIXTURE.replace("ARC-noyau: 80\n  - group: NTPLT", "ARC-noyau: pas-un-nombre\n  - group: NTPLT")
        bo = plan_lanes._MiniYamlParser(text).parse()
        failures = cbo.check_thresholds(bo)
        self.assertEqual(len(failures), 1)
        self.assertIn("non numérique", failures[0])

    def test_out_of_range_threshold_is_caught(self):
        text = VALID_FIXTURE.replace("NTPLT: 60\n      NTSEC: 60", "NTPLT: 150\n      NTSEC: 60")
        bo = plan_lanes._MiniYamlParser(text).parse()
        failures = cbo.check_thresholds(bo)
        self.assertTrue(any("hors [0, 100]" in f for f in failures))

    def test_negative_threshold_is_caught(self):
        text = VALID_FIXTURE.replace("NTPLT: 60\n      NTSEC: 60", "NTPLT: -5\n      NTSEC: 60")
        bo = plan_lanes._MiniYamlParser(text).parse()
        failures = cbo.check_thresholds(bo)
        self.assertTrue(any("hors [0, 100]" in f for f in failures))


class CheckOrphanPrefixesTests(unittest.TestCase):
    def test_real_repo_state_has_no_orphans(self):
        """The actual committed docs/BUILD_ORDER.yml, checked against the
        REAL plan-file inventory, must have zero orphans."""
        bo = plan_lanes.load_build_order(cbo.BUILD_ORDER_FILE)
        self.assertIsNotNone(bo, "docs/BUILD_ORDER.yml must exist for this repo state")
        failures = cbo.check_orphan_prefixes(bo)
        self.assertEqual(failures, [], f"orphaned prefixes found: {failures}")

    def test_covered_prefixes_resolves_direct_and_aliased_groups(self):
        bo = plan_lanes._MiniYamlParser(VALID_FIXTURE).parse()
        covered = cbo._covered_prefixes(bo)
        # NTPLT/NTSEC/NTAPI listed directly; ARC-noyau/ARC-sweep/SCA-gov
        # resolve via their alias "prefix" field to ARC/ARC/SCA.
        self.assertEqual(covered, {"NTPLT", "NTSEC", "NTAPI", "ARC", "SCA"})

    def test_injected_orphan_prefix_via_fake_inventory(self):
        """Simulate an orphan without touching the real plan files: monkeypatch
        plan_progress.progress() to return a prefix the fixture doesn't cover."""
        bo = plan_lanes._MiniYamlParser(VALID_FIXTURE).parse()
        orig = cbo.plan_progress.progress
        try:
            cbo.plan_progress.progress = lambda: {
                "ARC": {"done": 0, "total": 5, "pct": 0.0},
                "TOTALLY_UNCOVERED_PREFIX": {"done": 0, "total": 1, "pct": 0.0},
            }
            failures = cbo.check_orphan_prefixes(bo)
        finally:
            cbo.plan_progress.progress = orig
        self.assertEqual(len(failures), 1)
        self.assertIn("TOTALLY_UNCOVERED_PREFIX", failures[0])


class MainEndToEndTests(unittest.TestCase):
    def test_real_repo_state_is_green(self):
        exit_code = cbo.main([])
        self.assertEqual(exit_code, 0)

    def test_missing_file_is_green_not_red(self):
        """A missing BUILD_ORDER.yml (pre-SCA1 repo state) must never fail
        the build -- it's an optional file whose absence just means gating
        hasn't landed yet."""
        missing = Path(tempfile.mktemp(suffix=".yml"))
        exit_code = cbo.main([str(missing)])
        self.assertEqual(exit_code, 0)

    def test_injected_cycle_fails_the_build_specifically_on_the_cycle(self):
        # Insert INSIDE edges: (appending after unmapped_ok's list would
        # attach it there instead -- see CheckAcyclicTests.test_self_loop_is_caught).
        text = VALID_FIXTURE.replace(
            "\nunmapped_ok:",
            "  - group: NTAPI\n    wave: C\n    after:\n      NTAPI: 10\n\nunmapped_ok:",
        )
        path = _write(text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        # Isolate this to JUST the cycle check (fake the inventory to the
        # fixture's own coverage, so an unrelated real-repo orphan can't
        # make this pass for the wrong reason).
        orig = cbo.plan_progress.progress
        try:
            cbo.plan_progress.progress = lambda: {
                p: {"done": 0, "total": 1, "pct": 0.0}
                for p in ("ARC", "SCA", "NTPLT", "NTSEC", "NTAPI", "DC")
            }
            exit_code = cbo.main([str(path)])
        finally:
            cbo.plan_progress.progress = orig
        self.assertEqual(exit_code, 1)

    def test_injected_bad_threshold_fails_the_build_specifically_on_the_threshold(self):
        text = VALID_FIXTURE.replace("ARC-noyau: 80\n  - group: NTPLT", "ARC-noyau: pas-un-nombre\n  - group: NTPLT")
        path = _write(text)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        orig = cbo.plan_progress.progress
        try:
            cbo.plan_progress.progress = lambda: {
                p: {"done": 0, "total": 1, "pct": 0.0}
                for p in ("ARC", "SCA", "NTPLT", "NTSEC", "NTAPI", "DC")
            }
            exit_code = cbo.main([str(path)])
        finally:
            cbo.plan_progress.progress = orig
        self.assertEqual(exit_code, 1)

    def test_valid_fixture_alone_is_green(self):
        """The small VALID_FIXTURE only maps a handful of prefixes, so this
        must fake the real-inventory lookup to just the ones the fixture
        actually covers (+ DC, unmapped_ok) -- otherwise every OTHER real
        prefix in the live plan files would show up as "orphaned" against
        this tiny fixture, which is not what this test is checking."""
        path = _write(VALID_FIXTURE)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        orig = cbo.plan_progress.progress
        try:
            cbo.plan_progress.progress = lambda: {
                p: {"done": 0, "total": 1, "pct": 0.0}
                for p in ("ARC", "SCA", "NTPLT", "NTSEC", "NTAPI", "DC")
            }
            exit_code = cbo.main([str(path)])
        finally:
            cbo.plan_progress.progress = orig
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
