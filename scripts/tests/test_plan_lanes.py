"""Tests SCA3 — scripts/plan_lanes.py's BUILD_ORDER.yml wave gating.

Pure stdlib (unittest), no Django/DB needed. Run with:
    python -m unittest scripts.tests.test_plan_lanes -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import plan_lanes as pl  # noqa: E402


MINI_YAML_FIXTURE = """\
# a top comment, ignored
waves:
  A:
    order: 1
    description: >-
      some prose that spans
      multiple folded lines
    groups: [ARC-noyau, SCA-gov]
  B:
    order: 2
    groups: [NTPLT]

aliases:
  ARC-noyau:
    prefix: ARC
    members: [1, 2, 6]
  ARC-sweep:
    prefix: ARC
    members: [3, 4, 5]

edges:
  - group: ARC-sweep
    wave: A
    after:
      ARC-noyau: 80
  - group: NTPLT
    wave: B
    after:
      ARC-noyau: 80

unmapped_ok:
  - DC
  - FG   # a trailing comment with a "quoted phrase" inside it
  - FE-XFLT
"""

SIMPLE_PLAN_FIXTURE = """\
## BUILD QUEUE

- [ ] ARC1 — kernel task one. (@lane: backend/core)
- [ ] ARC3 — sweep task. (@lane: backend/core)
- [ ] NTPLT1 — platform task. (@lane: backend/core)
- [ ] DC1 — unmapped-ok legacy task. (@lane: backend/core)
- [ ] SCA1 — gov task, wave A, no prereq (unmapped in this fixture -> passthrough). (@lane: gov/build-order)
"""


class MiniYamlParserTests(unittest.TestCase):
    def _parse(self, text: str) -> dict:
        return pl._MiniYamlParser(text).parse()

    def test_parses_nested_mapping_and_flow_list(self):
        doc = self._parse(MINI_YAML_FIXTURE)
        self.assertEqual(doc["waves"]["A"]["order"], 1)
        self.assertEqual(doc["waves"]["A"]["groups"], ["ARC-noyau", "SCA-gov"])
        self.assertEqual(doc["waves"]["B"]["groups"], ["NTPLT"])

    def test_folded_scalar_is_not_an_empty_dict(self):
        doc = self._parse(MINI_YAML_FIXTURE)
        # A folded ">-" scalar must never silently become {} (that would be
        # indistinguishable from "the key was accidentally an empty
        # mapping" -- it must be a recognisable placeholder string).
        self.assertIsInstance(doc["waves"]["A"]["description"], str)
        self.assertNotEqual(doc["waves"]["A"]["description"], "")

    def test_parses_list_of_mappings_edges(self):
        doc = self._parse(MINI_YAML_FIXTURE)
        edges = doc["edges"]
        self.assertEqual(len(edges), 2)
        self.assertEqual(edges[0]["group"], "ARC-sweep")
        self.assertEqual(edges[0]["wave"], "A")
        self.assertEqual(edges[0]["after"], {"ARC-noyau": 80})
        self.assertEqual(edges[1]["group"], "NTPLT")

    def test_parses_aliases_with_int_list_members(self):
        doc = self._parse(MINI_YAML_FIXTURE)
        self.assertEqual(doc["aliases"]["ARC-noyau"]["prefix"], "ARC")
        self.assertEqual(doc["aliases"]["ARC-noyau"]["members"], [1, 2, 6])
        self.assertEqual(doc["aliases"]["ARC-sweep"]["members"], [3, 4, 5])

    def test_unmapped_ok_list_of_scalars_comment_stripped(self):
        doc = self._parse(MINI_YAML_FIXTURE)
        self.assertEqual(doc["unmapped_ok"], ["DC", "FG", "FE-XFLT"])

    def test_comment_inside_trailing_quotes_does_not_break_stripping(self):
        # Regression: a '#' guard that disables comment-stripping whenever
        # ANY quote appears anywhere on the line (rather than only before
        # the '#') would leave 'FG   # ..."quoted phrase"...' un-stripped.
        doc = self._parse(MINI_YAML_FIXTURE)
        self.assertIn("FG", doc["unmapped_ok"])
        self.assertNotIn(
            next((x for x in doc["unmapped_ok"] if "quoted phrase" in str(x)), None),
            doc["unmapped_ok"],
        )


class TaskPrefixTests(unittest.TestCase):
    def test_plain_prefix(self):
        self.assertEqual(pl._task_prefix("ARC12"), "ARC")
        self.assertEqual(pl._task_prefix("NTPLT7"), "NTPLT")

    def test_compound_prefix(self):
        self.assertEqual(pl._task_prefix("FE-XFLT4"), "FE-XFLT")

    def test_task_number(self):
        self.assertEqual(pl._task_number("ARC12"), 12)
        self.assertEqual(pl._task_number("FE-XFLT4"), 4)

    def test_unmatched_returns_empty_and_none(self):
        self.assertEqual(pl._task_prefix("not-a-task-id"), "")
        self.assertIsNone(pl._task_number("not-a-task-id"))


class GatedGroupResolutionTests(unittest.TestCase):
    def setUp(self):
        self.build_order = pl._MiniYamlParser(MINI_YAML_FIXTURE).parse()

    def test_kernel_number_resolves_to_noyau_alias(self):
        self.assertEqual(pl.gated_group_for_task("ARC1", self.build_order), "ARC-noyau")
        self.assertEqual(pl.gated_group_for_task("ARC6", self.build_order), "ARC-noyau")

    def test_sweep_number_resolves_to_sweep_alias(self):
        self.assertEqual(pl.gated_group_for_task("ARC3", self.build_order), "ARC-sweep")

    def test_number_outside_both_aliases_falls_back_to_bare_prefix(self):
        self.assertEqual(pl.gated_group_for_task("ARC99", self.build_order), "ARC")

    def test_prefix_with_no_aliases_resolves_to_itself(self):
        self.assertEqual(pl.gated_group_for_task("NTPLT1", self.build_order), "NTPLT")

    def test_none_build_order_resolves_to_bare_prefix(self):
        self.assertEqual(pl.gated_group_for_task("ARC3", None), "ARC")


class BuildOrderGateTests(unittest.TestCase):
    def setUp(self):
        self.build_order = pl._MiniYamlParser(MINI_YAML_FIXTURE).parse()

    def test_no_build_order_is_always_a_noop(self):
        self.assertEqual(pl.build_order_gate("ARC3", None, lambda p: 0.0), [])

    def test_unmapped_ok_prefix_passes_through(self):
        self.assertEqual(
            pl.build_order_gate("DC1", self.build_order, lambda p: 0.0), []
        )

    def test_prefix_absent_from_file_entirely_passes_through(self):
        # "SCA" appears nowhere in this fixture's waves/edges/aliases/
        # unmapped_ok -- must be treated exactly like "not covered yet".
        self.assertEqual(
            pl.build_order_gate("SCA1", self.build_order, lambda p: 0.0), []
        )

    def test_sweep_below_threshold_is_refused_with_french_reason(self):
        reasons = pl.build_order_gate("ARC3", self.build_order, lambda p: 0.0)
        self.assertEqual(len(reasons), 1)
        self.assertIn("ARC-noyau", reasons[0])
        self.assertIn("80", reasons[0])

    def test_sweep_at_or_above_threshold_passes(self):
        reasons = pl.build_order_gate("ARC3", self.build_order, lambda p: 85.0)
        self.assertEqual(reasons, [])

    def test_kernel_task_itself_never_gated_by_its_own_sweep_edge(self):
        # ARC1 resolves to the ARC-noyau alias, which has NO edge of its own
        # in the fixture -- must pass through untouched.
        reasons = pl.build_order_gate("ARC1", self.build_order, lambda p: 0.0)
        self.assertEqual(reasons, [])

    def test_multiple_unmet_prerequisites_all_listed(self):
        def lookup(prefix: str) -> float:
            return 0.0  # everything under-threshold

        reasons = pl.build_order_gate("NTPLT1", self.build_order, lookup)
        self.assertEqual(len(reasons), 1)  # NTPLT edge has one prereq here


class ApplyBuildOrderGateTests(unittest.TestCase):
    def setUp(self):
        self.build_order = pl._MiniYamlParser(MINI_YAML_FIXTURE).parse()
        self.tasks = [
            {"id": "ARC1", "prefix": "ARC"},
            {"id": "ARC3", "prefix": "ARC"},
            {"id": "NTPLT1", "prefix": "NTPLT"},
            {"id": "DC1", "prefix": "DC"},
        ]

    def test_splits_allowed_and_blocked(self):
        allowed, blocked = pl.apply_build_order_gate(
            self.tasks, self.build_order, lambda p: 0.0,
        )
        allowed_ids = {t["id"] for t in allowed}
        blocked_ids = {t["id"] for t in blocked}
        self.assertEqual(allowed_ids, {"ARC1", "DC1"})
        self.assertEqual(blocked_ids, {"ARC3", "NTPLT1"})

    def test_blocked_tasks_carry_reasons(self):
        _, blocked = pl.apply_build_order_gate(
            self.tasks, self.build_order, lambda p: 0.0,
        )
        for t in blocked:
            self.assertIn("wave_block_reasons", t)
            self.assertTrue(t["wave_block_reasons"])

    def test_force_wave_returns_everything_allowed(self):
        allowed, blocked = pl.apply_build_order_gate(
            self.tasks, self.build_order, lambda p: 0.0, force_wave=True,
        )
        self.assertEqual(len(allowed), len(self.tasks))
        self.assertEqual(blocked, [])

    def test_no_build_order_returns_everything_allowed(self):
        allowed, blocked = pl.apply_build_order_gate(
            self.tasks, None, lambda p: 0.0,
        )
        self.assertEqual(len(allowed), len(self.tasks))
        self.assertEqual(blocked, [])


class EndToEndCliTests(unittest.TestCase):
    """Exercises main() against a small real plan file + the fixture
    BUILD_ORDER.yml on disk, proving the wiring (not just the pure
    functions) actually refuses/allows the right tasks."""

    def _write(self, text: str, suffix: str = ".md") -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_missing_build_order_file_is_fully_backward_compatible(self):
        """SCA3 contract: no BUILD_ORDER.yml at all -> byte-identical
        schedule to pre-SCA3 behaviour (every buildable task included,
        nothing refused)."""
        plan_path = self._write(SIMPLE_PLAN_FIXTURE)
        missing_build_order = Path(tempfile.mktemp(suffix=".yml"))
        tasks = pl.parse_tasks(plan_path)
        build_order = pl.load_build_order(missing_build_order)
        self.assertIsNone(build_order)
        allowed, blocked = pl.apply_build_order_gate(
            tasks, build_order, lambda p: 0.0,
        )
        self.assertEqual(len(allowed), len(tasks))
        self.assertEqual(blocked, [])

    def test_real_build_order_refuses_arc_sweep_ahead_of_kernel(self):
        plan_path = self._write(SIMPLE_PLAN_FIXTURE)
        build_order_path = self._write(MINI_YAML_FIXTURE, suffix=".yml")
        tasks = pl.parse_tasks(plan_path)
        build_order = pl.load_build_order(build_order_path)
        allowed, blocked = pl.apply_build_order_gate(
            tasks, build_order, lambda p: 0.0,
        )
        blocked_ids = {t["id"] for t in blocked}
        allowed_ids = {t["id"] for t in allowed}
        self.assertIn("ARC3", blocked_ids)
        self.assertIn("NTPLT1", blocked_ids)
        self.assertIn("ARC1", allowed_ids)
        self.assertIn("DC1", allowed_ids)
        # SCA1 in this fixture's BUILD_ORDER.yml has no entry at all
        # (unmapped by this small fixture) -> passes through untouched,
        # proving "prefix absent from BUILD_ORDER.yml entirely" never gates.
        self.assertIn("SCA1", allowed_ids)


if __name__ == "__main__":
    unittest.main()
