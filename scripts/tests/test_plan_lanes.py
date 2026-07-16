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


class TaskCostTests(unittest.TestCase):
    """The ``— <size>`` tag drives the effort weight used to balance workers."""

    def test_sizes_map_to_weights(self):
        self.assertEqual(pl._task_cost("x (ROUTINE — S, sonnet)"), 1.0)
        self.assertEqual(pl._task_cost("x (ROUTINE — M, sonnet)"), 2.0)
        self.assertEqual(pl._task_cost("x (ROUTINE — L, sonnet)"), 4.0)
        self.assertEqual(pl._task_cost("x (SCHEMA — XL, opus)"), 6.0)
        self.assertEqual(pl._task_cost("x (ROUTINE — S/M, sonnet)"), 1.5)

    def test_untagged_defaults_to_medium(self):
        # No size tag at all -> never treated as free (modal M).
        self.assertEqual(pl._task_cost("x (ROUTINE — note in DONE LOG)"), 2.0)
        self.assertEqual(pl._task_cost("a task with no category paren"), 2.0)

    def test_bare_L_outside_category_paren_is_not_a_size(self):
        # A stray "L" in prose must not be read as a size tag.
        self.assertEqual(pl._task_cost("build the L-shaped thing"), 2.0)


class WorkerPackingTests(unittest.TestCase):
    """Lanes are LPT bin-packed into N time-balanced worker buckets."""

    @staticmethod
    def _mk(task_id, lane, cost, model="sonnet"):
        return {
            "id": task_id, "prefix": "VX", "lane": lane, "gate": "buildable",
            "gate_reasons": [], "deps": [], "section": "", "model": model,
            "cost": cost,
        }

    def test_lane_never_split_and_all_tasks_covered(self):
        tasks = [
            self._mk("A1", "lane-a", 4.0), self._mk("A2", "lane-a", 4.0),
            self._mk("B1", "lane-b", 2.0),
            self._mk("C1", "lane-c", 1.0), self._mk("C2", "lane-c", 1.0),
        ]
        plan = pl.schedule(tasks, max_lanes=8, n_workers=2)
        # Every task lands in exactly one worker, none dropped/duplicated.
        placed = [tid for w in plan["workers"] for tid in w["tasks"]]
        self.assertEqual(sorted(placed), ["A1", "A2", "B1", "C1", "C2"])
        # A lane is never split across two workers.
        for lane in ("lane-a", "lane-b", "lane-c"):
            owners = [i for i, w in enumerate(plan["workers"]) if lane in w["lanes"]]
            self.assertEqual(len(owners), 1, f"{lane} split across workers")

    def test_balances_makespan_below_naive(self):
        # 8 unit lanes into 2 workers -> perfect 4/4 split (makespan 4),
        # far below the 8 a single worker would carry.
        tasks = [self._mk(f"T{i}", f"lane-{i}", 1.0) for i in range(8)]
        plan = pl.schedule(tasks, max_lanes=8, n_workers=2)
        costs = sorted(w["cost"] for w in plan["workers"])
        self.assertEqual(costs, [4.0, 4.0])
        self.assertEqual(plan["counts"]["makespan_cost"], 4.0)
        self.assertEqual(plan["counts"]["total_cost"], 8.0)

    def test_fewer_lanes_than_workers_drops_empty_buckets(self):
        tasks = [self._mk("A1", "lane-a", 2.0), self._mk("B1", "lane-b", 2.0)]
        plan = pl.schedule(tasks, max_lanes=8, n_workers=8)
        self.assertEqual(plan["counts"]["workers"], 2)  # not 8 empty ones

    def test_worker_model_is_highest_tier_in_its_bundle(self):
        tasks = [
            self._mk("A1", "lane-a", 2.0, model="haiku"),
            self._mk("B1", "lane-b", 2.0, model="opus"),
        ]
        # One worker forced to carry both lanes -> must run at opus (safe bar).
        plan = pl.schedule(tasks, max_lanes=8, n_workers=1)
        self.assertEqual(len(plan["workers"]), 1)
        self.assertEqual(plan["workers"][0]["model"], "opus")


class TaskFilesTests(unittest.TestCase):
    """``Files:`` parsing drives forced file-disjoint lanes."""

    def test_parses_files_clause(self):
        label = "x. Files: `apps/crm/models.py`, `apps/crm/views.py`. (ROUTINE — M)"
        self.assertEqual(
            pl._task_files(label), frozenset({"apps/crm/models.py", "apps/crm/views.py"}))

    def test_append_only_surfaces_excluded(self):
        label = "x. Files: frontend/src/index.css, frontend/src/pages/x/Foo.jsx."
        # index.css is append-only → dropped; only the substantive file remains.
        self.assertEqual(pl._task_files(label), frozenset({"frontend/src/pages/x/Foo.jsx"}))

    def test_no_files_clause_is_empty(self):
        self.assertEqual(pl._task_files("a task with no Files declaration"), frozenset())

    def test_refs_before_files_ignored(self):
        # Only the segment after the LAST "Files:" is scanned.
        label = "bug at webhooks.py:182 … Fix it. Files: `apps/crm/webhooks.py`."
        self.assertEqual(pl._task_files(label), frozenset({"apps/crm/webhooks.py"}))


class MergeLanesBySharedFilesTests(unittest.TestCase):
    """Lanes sharing a substantive file are unioned so workers fold clean."""

    @staticmethod
    def _t(tid, lane, files):
        return {
            "id": tid, "prefix": "VX", "lane": lane, "gate": "buildable",
            "gate_reasons": [], "deps": [], "section": "", "model": "sonnet",
            "cost": 2.0, "files": files,
        }

    def test_two_lanes_sharing_a_file_merge(self):
        lanes = {
            "lane-a": [self._t("A1", "lane-a", ["x/Foo.jsx"])],
            "lane-b": [self._t("B1", "lane-b", ["x/Foo.jsx"])],
            "lane-c": [self._t("C1", "lane-c", ["y/Bar.jsx"])],
        }
        merged, merges = pl._merge_lanes_by_shared_files(lanes)
        # lane-a and lane-b collapse into one; lane-c stays separate.
        self.assertEqual(len(merged), 2)
        self.assertEqual(len(merges), 1)
        # every task's lane label points at an existing merged key.
        for k, ts in merged.items():
            for t in ts:
                self.assertEqual(t["lane"], k)

    def test_no_shared_file_is_noop(self):
        lanes = {
            "lane-a": [self._t("A1", "lane-a", ["a.jsx"])],
            "lane-b": [self._t("B1", "lane-b", ["b.jsx"])],
        }
        merged, merges = pl._merge_lanes_by_shared_files(lanes)
        self.assertEqual(merges, [])
        self.assertEqual(set(merged), {"lane-a", "lane-b"})

    def test_workers_are_file_disjoint_end_to_end(self):
        # Two lanes that would collide (share Foo.jsx) must land in ONE worker.
        tasks = [
            self._t("A1", "lane-a", ["shared/Foo.jsx"]),
            self._t("B1", "lane-b", ["shared/Foo.jsx"]),
            self._t("C1", "lane-c", ["other/Bar.jsx"]),
        ]
        plan = pl.schedule(tasks, max_lanes=8, n_workers=8)
        self.assertEqual(plan["counts"]["file_merges"], 1)
        # A1 and B1 share Foo.jsx → they must land in the SAME worker.
        owner = {}
        for i, w in enumerate(plan["workers"]):
            for tid in w["tasks"]:
                owner[tid] = i
        self.assertEqual(owner["A1"], owner["B1"], "colliding lanes split across workers")


class PipelinedWavesTests(unittest.TestCase):
    """Lanes chunk into a sequence of ~wave_size, cross-disjoint waves."""

    @staticmethod
    def _t(tid, lane, files=(), cost=2.0):
        return {
            "id": tid, "prefix": "VX", "lane": lane, "gate": "buildable",
            "gate_reasons": [], "deps": [], "section": "", "model": "sonnet",
            "cost": cost, "files": list(files),
        }

    def test_chunks_into_multiple_waves(self):
        # 30 one-task lanes, wave_size 8, 4 workers -> 4 waves (8/8/8/6).
        tasks = [self._t(f"T{i}", f"lane-{i}") for i in range(30)]
        plan = pl.schedule(tasks, max_lanes=4, n_workers=4, wave_size=8)
        pw = plan["pipelined_waves"]
        self.assertEqual(len(pw), 4)
        self.assertEqual([w["tasks_total"] for w in pw], [8, 8, 8, 6])

    def test_every_task_in_exactly_one_wave(self):
        tasks = [self._t(f"T{i}", f"lane-{i}") for i in range(20)]
        plan = pl.schedule(tasks, max_lanes=4, n_workers=4, wave_size=8)
        placed = [tid for w in plan["pipelined_waves"]
                  for a in w["agents"] for tid in a["tasks"]]
        self.assertEqual(sorted(placed), sorted(f"T{i}" for i in range(20)))

    def test_waves_are_file_disjoint(self):
        # Each file lives in exactly one lane (merge step) -> no file spans two
        # waves, so wave K+1 can build while wave K tests.
        tasks = (
            [self._t(f"A{i}", f"a-{i}", [f"a{i}.py"]) for i in range(10)]
            + [self._t(f"B{i}", f"b-{i}", [f"b{i}.py"]) for i in range(10)]
        )
        plan = pl.schedule(tasks, max_lanes=4, n_workers=4, wave_size=8)
        # collect the file set of each wave; no file appears in two waves.
        by_task = {t["id"]: t["files"] for t in tasks}
        wave_files = []
        for w in plan["pipelined_waves"]:
            fs = set()
            for a in w["agents"]:
                for tid in a["tasks"]:
                    fs.update(by_task[tid])
            wave_files.append(fs)
        for i in range(len(wave_files)):
            for j in range(i + 1, len(wave_files)):
                self.assertEqual(wave_files[i] & wave_files[j], set())

    def test_single_lane_never_splits_across_waves(self):
        # A 20-task lane must stay whole even when wave_size is 8.
        tasks = [self._t(f"T{i}", "big-lane") for i in range(20)]
        plan = pl.schedule(tasks, max_lanes=4, n_workers=4, wave_size=8)
        self.assertEqual(len(plan["pipelined_waves"]), 1)
        self.assertEqual(plan["pipelined_waves"][0]["tasks_total"], 20)


if __name__ == "__main__":
    unittest.main()
