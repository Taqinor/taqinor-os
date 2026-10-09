"""Tests SCA3 — scripts/plan_lanes.py's BUILD_ORDER.yml wave gating.

Pure stdlib (unittest), no Django/DB needed. Run with:
    python -m unittest scripts.tests.test_plan_lanes -v
"""
import contextlib
import io
import json
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

    def test_toute_extension_lue_et_json_non_tronque(self):
        # Critique finale OWN : l'ancienne regex ne connaissait pas `.astro`
        # ni `.ts`, et coupait `.json` en `.js` — deux tâches sur la même page
        # Astro ou le même contrat JSON n'étaient pas unies et se percutaient.
        label = ("x. Files: `apps/web/src/pages/proposition/[...token].astro`, "
                 "`backend/django_core/apps/ventes/contract_samples/calepinage_options.json`, "
                 "`apps/web/src/lib/lead.ts`. (ROUTINE)")
        attendus = frozenset({
            "apps/web/src/pages/proposition/[...token].astro",
            "backend/django_core/apps/ventes/contract_samples/calepinage_options.json",
            "apps/web/src/lib/lead.ts"})
        self.assertEqual(pl._task_files(label), attendus)
        self.assertEqual(pl._task_files_brut(label), attendus)

    def test_balise_at_files_ne_masque_pas_la_clause_files(self):
        # `(@files: …)` est une balise de LANE, pas la clause Files: — placée
        # après, elle ne doit pas faire oublier la vraie liste de fichiers.
        label = ("x. Files: `apps/crm/models.py`, `apps/crm/views.py`. (ROUTINE) "
                 "(@files: apps/crm/models.py)")
        self.assertEqual(pl._task_files(label),
                         frozenset({"apps/crm/models.py", "apps/crm/views.py"}))

    def test_nom_nu_reste_une_cle_de_lane(self):
        # Prudence : un nom sans dossier (`veille_couverture.json`, cité par
        # plusieurs tâches de PLAN_VEILLE) est ambigu pour la garde, mais deux
        # tâches qui le nomment peuvent éditer le même fichier : il continue
        # d'unir leurs lanes, avec sa VRAIE extension.
        label = "x. Files: `apps/adsengine/competitor_intel.py`, `veille_couverture.json`. (ROUTINE)"
        self.assertEqual(pl._task_files(label), frozenset({
            "apps/adsengine/competitor_intel.py", "veille_couverture.json"}))

    def test_deux_taches_partageant_une_page_astro_sont_unies(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "WEB_PLAN.md"
            plan.write_text(
                "## BUILD QUEUE\n"
                "- [ ] W1 — a. Files: `apps/web/src/pages/devis/mon-toit.astro`. "
                "(ROUTINE) (@lane: web-a)\n"
                "- [ ] W2 — b. Files: `apps/web/src/pages/devis/mon-toit.astro`, "
                "`apps/web/src/lib/x.ts`. (ROUTINE) (@lane: web-b)\n",
                encoding="utf-8")
            taches = pl.parse_tasks(plan)
        planif = pl.schedule(taches, max_lanes=8)
        self.assertEqual(len(planif["lanes"]), 1, planif["lanes"])
        self.assertEqual(planif["counts"]["file_merges"], 1)


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


class DependancesBloqueesEtOrdreTests(unittest.TestCase):
    """Incident du 07/10/2026 (plan audit calepinage) : ACAL96 partait avant
    ACAL42 (bloquée), et ACAL102 avant ACAL101 dans la même lane."""

    @staticmethod
    def _t(tid, lane, deps=(), gate="buildable", files=()):
        return {
            "id": tid, "prefix": "ACAL", "lane": lane, "gate": gate,
            "gate_reasons": [], "deps": set(deps), "section": "",
            "model": "sonnet", "cost": 2.0, "files": list(files),
        }

    def test_dependance_bloquee_du_meme_run_refuse_la_tache_et_sa_suite(self):
        tasks = [
            self._t("ACAL42", "a", gate="gated"),
            self._t("ACAL96", "b", deps=["ACAL42"]),
            self._t("ACAL100", "b", deps=["ACAL96"]),
            self._t("ACAL98", "c"),
        ]
        ok, refusees = pl.apply_external_after_gate(tasks, index={})
        self.assertEqual({t["id"] for t in refusees}, {"ACAL96", "ACAL100"})
        self.assertIn("ACAL42", {t["id"] for t in ok})     # reste « gated »
        self.assertIn("ACAL98", {t["id"] for t in ok})
        self.assertIn("[BLOCKED]", refusees[0]["after_block_reasons"][0])

    def test_force_wave_laisse_passer(self):
        tasks = [self._t("ACAL42", "a", gate="gated"),
                 self._t("ACAL96", "b", deps=["ACAL42"])]
        ok, refusees = pl.apply_external_after_gate(tasks, {}, force_wave=True)
        self.assertEqual(refusees, [])

    def test_lane_fusionnee_suit_les_after_pas_l_ordre_du_fichier(self):
        tasks = [
            self._t("ACAL102", "x", deps=["ACAL101"], files=["f.py"]),
            self._t("ACAL96", "y", files=["f.py"]),
            self._t("ACAL101", "y", deps=["ACAL96"], files=["f.py"]),
        ]
        plan = pl.schedule(tasks, max_lanes=8, n_workers=1)
        ordre = [tid for w in plan["waves"] for tid in w]
        self.assertLess(ordre.index("ACAL96"), ordre.index("ACAL101"))
        self.assertLess(ordre.index("ACAL101"), ordre.index("ACAL102"))


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


class ContractPairingGateTests(unittest.TestCase):
    """PACT11 — le refus est testé sur le CAS RÉEL AOF172 / AOF166.

    Ligne à ligne, ce qui s'est passé le 03/08/2026 : la tâche de l'écran du
    tableau de bord AO (AOF172) déclarait dépendre de la tâche de la LISTE des
    affaires (AOF170) — et PAS de AOF166, la tâche backend qui produit
    exactement les données qu'il affiche. La dépendance existait dans la
    réalité, elle n'a jamais été écrite, donc les deux tâches ont été
    planifiées SIMULTANÉMENT et chaque moitié a inventé son contrat.
    """

    AOF166 = ("- [ ] AOF166 — KPI d'appels d'offres + tableau de bord des "
              "marchés. Files: `backend/django_core/apps/ao/selectors.py`, "
              "`backend/django_core/apps/ao/urls.py`. (ARCH) (@lane: ao-back)")
    # AOF170 porte `@after: AOF166` : c'est la déclaration qui MANQUAIT sur
    # AOF172. Elle sert ici de témoin — la même tâche, correctement déclarée,
    # passe la porte.
    AOF170 = ("- [ ] AOF170 — Liste des affaires. "
              "Files: `frontend/src/features/ao/AffairesList.jsx`. "
              "(ROUTINE) (@lane: ao-front) (@after: AOF166)")
    AOF172_SANS = ("- [ ] AOF172 — Écran du tableau de bord AO. "
                   "Files: `frontend/src/features/ao/DashboardPage.jsx`, "
                   "`frontend/src/api/aoApi.js`. (ROUTINE) (@lane: ao-front) "
                   "(@after: AOF170)")
    AOF172_AVEC = AOF172_SANS.replace("(@after: AOF170)",
                                      "(@after: AOF170, AOF166)")

    def _tasks(self, *lignes):
        chemin = Path(tempfile.mkdtemp()) / "PLAN.md"
        chemin.write_text("## BUILD QUEUE\n\n" + "\n".join(lignes) + "\n",
                          encoding="utf-8")
        self.addCleanup(lambda: chemin.unlink(missing_ok=True))
        return pl.parse_tasks(chemin)

    def test_le_cas_reel_AOF172_sans_after_sur_AOF166_est_REFUSE(self):
        tasks = self._tasks(self.AOF166, self.AOF170, self.AOF172_SANS)
        allowed, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual([t["id"] for t in blocked], ["AOF172"])
        self.assertEqual(sorted(t["id"] for t in allowed), ["AOF166", "AOF170"])
        motif = " ".join(blocked[0]["pairing_block_reasons"])
        self.assertIn("AOF166", motif)
        self.assertIn("FRONTEND", motif)
        self.assertIn("apps/ao/urls.py", motif)

    def test_avec_after_sur_AOF166_la_tache_passe(self):
        tasks = self._tasks(self.AOF166, self.AOF170, self.AOF172_AVEC)
        allowed, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual(blocked, [])
        self.assertEqual(len(allowed), 3)

    def test_sans_la_tache_backend_dans_le_run_rien_n_est_refuse(self):
        # L'écran seul (le backend est déjà sur `main`) : aucune raison de
        # refuser. La porte ne parle QUE du parallélisme d'un même run.
        tasks = self._tasks(self.AOF170, self.AOF172_SANS)
        allowed, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual(blocked, [])
        self.assertEqual(len(allowed), 2)

    def test_une_tache_backend_BLOQUEE_ne_refuse_rien(self):
        # Cas réel du pool de tous les plans : NTPRT29 `[BLOCKED: …]` dans
        # new_tasks_plan.md refusait 33 écrans crm de PLAN.md. Une tâche
        # bloquée ne part pas dans ce run, donc elle ne produit rien en
        # parallèle.
        bloquee = self.AOF166.replace(
            "AOF166 — ", "AOF166 — **[BLOCKED: décision fondateur]** ")
        tasks = self._tasks(bloquee, self.AOF170, self.AOF172_SANS)
        _, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual(blocked, [])

    def test_une_autre_app_n_est_jamais_appariee(self):
        # Le backend `crm` ne produit rien pour l'écran `ao` : appariement par
        # APP, jamais par proximité dans le fichier de plan.
        crm = ("- [ ] X1 — selectors crm. "
               "Files: `backend/django_core/apps/crm/selectors.py`. (ARCH)")
        tasks = self._tasks(crm, self.AOF172_SANS)
        _, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual(blocked, [])

    def test_une_tache_backend_qui_ne_touche_ni_urls_ni_selectors_ne_gate_pas(self):
        # Une migration ou un modèle ne PRODUIT pas de contrat d'API : seules
        # les routes (`urls.py`) et les agrégats (`selectors.py`) le font.
        modeles = ("- [ ] X2 — modèle AO. "
                   "Files: `backend/django_core/apps/ao/models.py`. (SCHEMA)")
        tasks = self._tasks(modeles, self.AOF172_SANS)
        _, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual(blocked, [])

    def test_un_fichier_de_test_nomme_selectors_n_est_pas_un_producteur(self):
        # ACAL350 : `tests/test_selectors.py` / `test_urls.py` finissent par
        # « selectors.py » / « urls.py » mais ne produisent aucun contrat.
        for chemin in ("backend/django_core/apps/ao/tests/test_selectors.py",
                       "backend/django_core/apps/ao/tests/test_urls.py"):
            back = (f"- [ ] X4 — tests AO. Files: `{chemin}`. (ROUTINE)")
            front = ("- [ ] X5 — écran AO. "
                     "Files: `frontend/src/features/ao/Ecran.jsx`. (ROUTINE)")
            tasks = self._tasks(back, front)
            _, blocked = pl.apply_contract_pairing_gate(tasks)
            self.assertEqual(blocked, [], chemin)

    def test_urls_py_et_selectors_py_restent_producteurs(self):
        # Non-régression ACAL350 : le cas réel AOF172 reste refusé, que le
        # producteur soit `urls.py` ou `selectors.py`.
        for chemin in ("backend/django_core/apps/ao/urls.py",
                       "backend/django_core/apps/ao/selectors.py"):
            back = (f"- [ ] AOF166 — KPI AO. Files: `{chemin}`. (ARCH)")
            tasks = self._tasks(back, self.AOF172_SANS)
            _, blocked = pl.apply_contract_pairing_gate(tasks)
            self.assertEqual([t["id"] for t in blocked], ["AOF172"], chemin)

    def test_une_tache_MIXTE_n_est_jamais_refusee_contre_elle_meme(self):
        # Les deux moitiés dans la MÊME ligne `Files:` : elle porte déjà son
        # propre contrat, il n'y a aucun parallélisme à empêcher (PACT12).
        mixte = ("- [ ] X3 — endpoint + écran. "
                 "Files: `backend/django_core/apps/ao/urls.py`, "
                 "`frontend/src/features/ao/Ecran.jsx`. (ARCH)")
        tasks = self._tasks(mixte)
        allowed, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual(blocked, [])
        self.assertEqual(len(allowed), 1)

    def test_force_wave_outrepasse_la_porte(self):
        tasks = self._tasks(self.AOF166, self.AOF170, self.AOF172_SANS)
        allowed, blocked = pl.apply_contract_pairing_gate(tasks, force_wave=True)
        self.assertEqual(blocked, [])
        self.assertEqual(len(allowed), 3)

    def test_sans_lignes_Files_le_comportement_est_inchange(self):
        # Rétro-compatibilité stricte : un plan sans `Files:` ne peut rien
        # apparier, donc la porte est un no-op exact.
        tasks = self._tasks("- [ ] Y1 — quelque chose. (ROUTINE) (@lane: a)",
                            "- [ ] Y2 — autre chose. (ROUTINE) (@lane: b)")
        allowed, blocked = pl.apply_contract_pairing_gate(tasks)
        self.assertEqual(blocked, [])
        self.assertEqual(len(allowed), 2)

    def test_le_refus_est_surface_dans_le_plan_rendu(self):
        tasks = self._tasks(self.AOF166, self.AOF170, self.AOF172_SANS)
        allowed, blocked = pl.apply_contract_pairing_gate(tasks)
        plan = pl.schedule(allowed, max_lanes=4, pairing_blocked=blocked)
        self.assertEqual(plan["counts"]["pairing_blocked"], 1)
        rendu = pl.render(plan, 4, "PLAN.md")
        self.assertIn("PACT11", rendu)
        self.assertIn("AOF172", rendu)
        self.assertIn("--force-wave", rendu)

    def test_les_fichiers_bruts_gardent_les_surfaces_append_only(self):
        # `files` retire index.css & co. pour ne pas fusionner deux lanes ;
        # `files_bruts` doit les garder, sinon un écran déclaré uniquement via
        # `router/index.jsx` échapperait à l'appariement.
        tache = ("- [ ] Z1 — écran. Files: `frontend/src/api/aoApi.js`, "
                 "`frontend/src/index.css`. (ROUTINE)")
        t = self._tasks(tache)[0]
        self.assertNotIn("frontend/src/index.css", t["files"])
        self.assertIn("frontend/src/index.css", t["files_bruts"])


class TaskLineGrammarTests(unittest.TestCase):
    """Les 4 formes de ligne que `_TASK_LIST_RE` rejetait — cas RÉELS du dépôt.

    Une ligne rejetée n'est pas seulement « mal formée » : elle est INVISIBLE
    au planificateur, donc sa tâche ne peut jamais être construite. Les quatre
    causes, telles que mesurées :

    (A) identifiant à tiret   — `FE-XFLT4` (docs/FRONTEND_GAP_PLAN.md, 145 tâches) ;
    (B) lettres/chiffres      — `NTP2P27`, `NTI18N53` (docs/new_tasks_plan.md) ;
        entrelacés
    (C) `[BLOCKED: …]` posé   — `NTPLT11` (docs/new_tasks_plan.md:571) ;
        entre l'id et le tiret
    (D) crochet imbriqué dans — `VX198` (docs/PLAN2.md:502) ; et une parenthèse
        le statut                d'annotation entre `]` et l'id (`PACT148`, `EZ17`).
    """

    # (A) — verbatim de docs/FRONTEND_GAP_PLAN.md (labels raccourcis).
    A_SIMPLE = ("- [ ] FE-XFLT4 — onglet « Cycle de vie » dans "
                "`VehiculeDetail.jsx`. (@lane: frontend/flotte)")
    A_PLAGE = ("- [ ] FE-XFLT1-3 — onglets « Contrats » + « Grand livre ». "
               "(@lane: frontend/flotte)")
    A_SLASH = ("- [ ] FE-XFLT7/15/18 — onglet « Analyse des coûts » + tuiles. "
               "(@lane: frontend/flotte)")
    A_SANS_CHIFFRE = ("- [ ] FE-notes-frais — écran des notes de frais. "
                      "(@lane: frontend/compta)")
    # (B) — verbatim de docs/new_tasks_plan.md.
    B_NTP2P = ("- [ ] NTP2P27 — **Réception partielle sur commande d'achat** : "
               "nouveau modèle `stock.ReceptionLigne`. (SCHEMA)")
    B_NTI18N = ("- [ ] NTI18N53 — **Pluralisation ICU côté écran**. (ROUTINE)")
    # (C) — docs/new_tasks_plan.md:571, l'annotation posée APRÈS l'identifiant.
    C_BLOQUEE = ("- [ ] NTPLT11 [BLOCKED: hors périmètre core-lane — migre des "
                 "abonnés de apps/crm+notifications+publicapi vers "
                 "subscribe_durable; à faire par les lanes domaine] — "
                 "**Basculer les effets non-critiques sur l'outbox**. (ARCH)")
    # Le TÉMOIN de (C) : la même tâche SANS l'annotation doit, elle, passer.
    C_TEMOIN = ("- [ ] NTPLT11 — **Basculer les effets non-critiques sur "
                "l'outbox**. (ARCH)")
    # (D) — docs/PLAN2.md:502 : le statut cite un AUTRE marqueur entre crochets.
    D_IMBRIQUE = ("- [BLOCKED: dev-dep manquante — `eslint-plugin-jsx-a11y` "
                  "absent ; la tâche elle-même se marque [GATED si dev-dep à "
                  "ajouter]] VX198 — **Garde statique jsx-a11y ciblée**.")
    # (D bis) — docs/PLAN.md:579 / docs/PLAN2.md:890 : parenthèse d'annotation
    # glissée entre la case et l'identifiant.
    D_PARENTHESE = ("- [x] (déjà présent — 120/120 vérifiées) PACT148 — "
                    "**Atteignabilité exigée sur les 120 tâches §E.**")
    D_PARENTHESE_2 = ("- [x] (déjà présent — origin/main@6773842e) EZ17 — "
                      "**La gate des trajets.**")
    # Contrôle NÉGATIF : un mot de prose nu n'est PAS un identifiant. Sans
    # chiffre ni séparateur, la ligne doit rester rejetée — un faux positif
    # dans le planificateur est plus grave qu'une tâche en attente.
    NEGATIF = "- [ ] TODO — revoir cette section avant la prochaine vague."

    def _plan(self, *lignes) -> Path:
        chemin = Path(tempfile.mkdtemp()) / "PLAN.md"
        chemin.write_text("## BUILD QUEUE\n\n" + "\n".join(lignes) + "\n",
                          encoding="utf-8")
        self.addCleanup(lambda: chemin.unlink(missing_ok=True))
        return chemin

    def _ids(self, *lignes) -> list[str]:
        return [t["id"] for t in pl.parse_tasks(self._plan(*lignes))]

    # --- (A) identifiants à tiret ------------------------------------------
    def test_A_identifiant_a_tiret_est_ordonnancable(self):
        self.assertEqual(
            self._ids(self.A_SIMPLE, self.A_PLAGE, self.A_SLASH,
                      self.A_SANS_CHIFFRE),
            ["FE-XFLT4", "FE-XFLT1-3", "FE-XFLT7/15/18", "FE-notes-frais"],
        )

    def test_A_le_prefixe_compose_reste_lisible_par_le_gating(self):
        # `_TASK_ID_PREFIX_RE` attendait DÉJÀ la forme composée : l'id parsé
        # doit donc retomber sur la même clé que scripts/plan_progress.py.
        self.assertEqual(pl._task_prefix(self._ids(self.A_SIMPLE)[0]),
                         "FE-XFLT")

    def test_A_aucune_ligne_mal_formee(self):
        self.assertEqual(
            pl.count_malformed(self._plan(self.A_SIMPLE, self.A_PLAGE,
                                          self.A_SLASH, self.A_SANS_CHIFFRE)),
            0,
        )

    # --- (B) lettres et chiffres entrelacés --------------------------------
    def test_B_identifiant_alphanumerique_entrelace(self):
        self.assertEqual(self._ids(self.B_NTP2P, self.B_NTI18N),
                         ["NTP2P27", "NTI18N53"])

    def test_B_aucune_ligne_mal_formee(self):
        self.assertEqual(
            pl.count_malformed(self._plan(self.B_NTP2P, self.B_NTI18N)), 0)

    # --- (C) `[BLOCKED: …]` en ligne ---------------------------------------
    def test_C_la_ligne_est_lue_et_non_plus_signalee_mal_formee(self):
        self.assertEqual(pl.count_malformed(self._plan(self.C_BLOQUEE)), 0)
        m = pl._TASK_LIST_RE.match(self.C_BLOQUEE)
        self.assertIsNotNone(m)
        self.assertEqual(m.group("id"), "NTPLT11")
        self.assertTrue(m.group("inline_status").startswith("BLOCKED:"))

    def test_C_le_BLOCKED_en_ligne_rend_la_tache_BLOQUEE(self):
        # Le point qui compte : élargir la regex ne doit SURTOUT PAS rendre
        # ordonnançable une tâche marquée « hors périmètre ». L'annotation
        # passe par le même chemin que le statut de la case.
        self.assertEqual(self._ids(self.C_BLOQUEE), [])

    def test_C_sans_l_annotation_la_meme_tache_passe(self):
        # Le témoin : c'est bien l'annotation qui bloque, pas l'élargissement.
        self.assertEqual(self._ids(self.C_TEMOIN), ["NTPLT11"])

    def test_C_la_case_BLOCKED_et_l_annotation_en_ligne_sont_equivalentes(self):
        en_case = "- [BLOCKED: hors périmètre] NTPLT11 — **Outbox**. (ARCH)"
        self.assertEqual(self._ids(en_case), self._ids(self.C_BLOQUEE))

    def test_C_une_tache_bloquee_ne_masque_pas_ses_voisines(self):
        self.assertEqual(self._ids(self.B_NTP2P, self.C_BLOQUEE,
                                   self.B_NTI18N),
                         ["NTP2P27", "NTI18N53"])

    # --- (D) crochet imbriqué / parenthèse d'annotation ---------------------
    def test_D_statut_a_crochet_imbrique_est_lu_en_entier(self):
        m = pl._TASK_LIST_RE.match(self.D_IMBRIQUE)
        self.assertIsNotNone(m)
        self.assertEqual(m.group("id"), "VX198")
        # Le statut doit contenir le marqueur imbriqué EN ENTIER, sinon il est
        # tronqué au premier `]` et la ligne redevient illisible.
        self.assertIn("[GATED si dev-dep à ajouter]", m.group("status"))

    def test_D_la_tache_au_statut_BLOCKED_reste_hors_du_planning(self):
        self.assertEqual(self._ids(self.D_IMBRIQUE), [])

    def test_D_parenthese_d_annotation_entre_la_case_et_l_identifiant(self):
        for ligne, task_id in ((self.D_PARENTHESE, "PACT148"),
                               (self.D_PARENTHESE_2, "EZ17")):
            with self.subTest(ligne=task_id):
                m = pl._TASK_LIST_RE.match(ligne)
                self.assertIsNotNone(m)
                self.assertEqual(m.group("id"), task_id)
                self.assertEqual(m.group("status"), "x")
                self.assertIn("déjà présent", m.group("note"))

    def test_D_aucune_ligne_mal_formee(self):
        self.assertEqual(
            pl.count_malformed(self._plan(self.D_IMBRIQUE, self.D_PARENTHESE,
                                          self.D_PARENTHESE_2)),
            0,
        )

    def test_check_pool_compte_chaque_fichier(self):
        # ADEP28 : `a.md b.md --check` doit compter les lignes mal formees de
        # CHAQUE fichier du pool (avant : seulement du premier).
        saine = self._plan("- [ ] ZZADEP28 — **Tache saine.** (@lane: apps/zz)")
        bancale = self._plan(self.NEGATIF)

        def lancer(*fichiers):
            sortie = io.StringIO()
            with contextlib.redirect_stderr(sortie), \
                    contextlib.redirect_stdout(io.StringIO()):
                return pl.main([*map(str, fichiers), "--check"])
        self.assertEqual(lancer(saine), 0)
        self.assertEqual(lancer(bancale), 1)
        self.assertEqual(lancer(saine, bancale), 1)
        self.assertEqual(lancer(bancale, saine), 1)

    # --- contrôle négatif ---------------------------------------------------
    def test_NEGATIF_un_mot_de_prose_n_est_pas_un_identifiant(self):
        self.assertIsNone(pl._TASK_LIST_RE.match(self.NEGATIF))
        journal = io.StringIO()
        with contextlib.redirect_stderr(journal):
            ids = self._ids(self.NEGATIF)
        self.assertEqual(ids, [])
        # …et elle reste SIGNALÉE, pas avalée en silence.
        self.assertIn("malformed task line", journal.getvalue())
        self.assertEqual(pl.count_malformed(self._plan(self.NEGATIF)), 1)

    def test_NEGATIF_autres_formes_de_prose_restent_rejetees(self):
        for ligne in (
            "- [ ] Revoir la section — puis relancer la vague.",
            "- [ ] Multi tenant — vérifier le scope company.",
            "- [Meta Advertising Standards](https://x.example) — consulté.",
        ):
            with self.subTest(ligne=ligne):
                self.assertIsNone(pl._TASK_LIST_RE.match(ligne))

    # --- non-régression -----------------------------------------------------
    def test_les_formes_historiques_parsent_toujours(self):
        self.assertEqual(
            self._ids("- [ ] N14 — une tâche simple. (ROUTINE)",
                      "- [ ] **A1** — une tâche en gras. (ROUTINE)",
                      "- [x] Z9 — une tâche cochée. (ROUTINE)",
                      "- [BLOCKED: raison] N26 — une tâche bloquée. (ROUTINE)"),
            ["N14", "A1"],
        )


class MarqueurGateEnTeteDeLabelTests(unittest.TestCase):
    """Un ``[BLOCKED: …]``/``[GATED: …]`` posé APRÈS le tiret cadratin est un
    état de tâche (formes réelles de NTUX21 et QXG6, émises buildables à tort
    le 2026-08-31 → une lane worktree entière a tourné pour rien) ; une tâche
    qui CITE un marqueur au milieu de son texte (VX198) reste buildable."""

    def _plan(self, *lignes) -> Path:
        chemin = Path(tempfile.mkdtemp()) / "PLAN.md"
        chemin.write_text("## BUILD QUEUE\n\n" + "\n".join(lignes) + "\n",
                          encoding="utf-8")
        self.addCleanup(lambda: chemin.unlink(missing_ok=True))
        return chemin

    def _gates(self, *lignes) -> dict:
        return {t["id"]: t["gate"] for t in pl.parse_tasks(self._plan(*lignes))}

    def test_blocked_apres_le_tiret_est_gated(self):
        # Forme réelle NTUX21 : annotation nue après le tiret, avant le titre.
        gates = self._gates(
            "- [ ] NTUX901 — [BLOCKED: attend NTUX12 — le widget Favoris "
            "n'existe pas côté frontend] **Réordonnancement** : glisser-"
            "déposer des favoris. (@lane: apps/uxviews) (ROUTINE)")
        self.assertEqual(gates, {"NTUX901": "gated"})

    def test_gated_en_gras_apres_le_tiret_est_gated(self):
        # Forme réelle QXG6 : marqueur en gras juste après le tiret.
        gates = self._gates(
            "- [ ] QXG901 — **[GATED: vérifs fondateur avant hard-coding]** "
            "(a) tarifs MT ONEE exacts. (@lane: apps/ventes) (DECISION)")
        self.assertEqual(gates, {"QXG901": "gated"})

    def test_note_parenthesee_apres_l_id_parse_sans_avertissement(self):
        # Forme réelle NTEXT26 : ``- [x] NTEXT26 (déjà présent) — …`` — la
        # ligne doit parser (tâche cochée, donc absente du schedule) au lieu
        # de spammer le canal « malformed task line ».
        chemin = self._plan(
            "- [x] NTEXT901 (déjà présent) — **Action custom** : détail. "
            "(@lane: apps/customfields) (ROUTINE)")
        self.assertEqual(pl.count_malformed(chemin), 0)
        self.assertEqual(pl.parse_tasks(chemin), [])

    def test_section_manuel_prefixee_d_un_groupe_hors_file(self):
        # Forme réelle PLAN.md « ### CAD — MANUEL (Reda / Meryem, pas du
        # code) » : ses tâches CADM étaient émises buildables (2026-09-28).
        chemin = Path(tempfile.mkdtemp()) / "PLAN.md"
        chemin.write_text(
            "## BUILD QUEUE\n\n### CAD — MANUEL (Reda / Meryem, pas du code)\n"
            "- [ ] CADM901 — **Relecture darija.** (@lane: apps/parametres)\n"
            "### Lot 7 — WORKFLOW (CALX901 ; CALX902 en GATED) — merge M5\n"
            "- [ ] CALX901 — **Tâche vivante.** (@lane: apps/calepinage)\n",
            encoding="utf-8")
        self.addCleanup(lambda: chemin.unlink(missing_ok=True))
        self.assertEqual([t["id"] for t in pl.parse_tasks(chemin)],
                         ["CALX901"])

    def test_citation_d_un_marqueur_en_milieu_de_texte_reste_buildable(self):
        # Forme VX198 : la tâche cite un marqueur dans son corps — vivante.
        gates = self._gates(
            "- [ ] VX901 — **Tâche vivante** : quand le cas se présente, la "
            "tâche elle-même se marque [GATED si dev-dep à ajouter] puis "
            "continue. (@lane: frontend/shell) (ROUTINE)")
        self.assertEqual(gates, {"VX901": "buildable"})


class PorteeTests(unittest.TestCase):
    """PORTÉE (``--only`` / ``--group``, 09/10/2026) — testée sur le CAS RÉEL EDC.

    Le groupe EDC de docs/plans/PLAN_AUDIT_TRANSVERSE.md (11 tâches d'écran
    pur sur l'éditeur de devis, SANS moitié backend) était refusé EN BLOC par
    PACT11 : AFAC17 / AFAC19 / APRF23 / APRF24 (backend ventes) vivent dans le
    même fichier, donc comptaient comme « le même run » — alors que la session
    ne drainait que le groupe EDC. La portée restreint l'ensemble AVANT les
    portes ; sans option, rien ne change (le refus d'origine reste le témoin).
    """

    AFAC17 = ("- [ ] AFAC17 — gestes de correction d'un paiement. "
              "Files: `backend/django_core/apps/ventes/views/paiement.py`, "
              "`backend/django_core/apps/ventes/selectors.py`. (SCHEMA) "
              "(@lane: afac/encaissement)")
    APRF23 = ("- [ ] APRF23 — sélecteur `devis_envoyes_expirant`. "
              "Files: `backend/django_core/apps/crm/selectors.py`, "
              "`backend/django_core/apps/ventes/selectors.py`. (ROUTINE) "
              "(@lane: aprf-crm/selecteurs)")
    EDC2 = ("- [ ] EDC2 — bouton « Dupliquer la ligne » dans l'éditeur. "
            "Files: `frontend/src/pages/ventes/DevisGenerator.jsx`. (ROUTINE) "
            "(@lane: edc/editeur)")
    EDC3 = ("- [ ] EDC3 — raccourcis clavier de l'éditeur. "
            "Files: `frontend/src/features/ventes/EditeurLignes.jsx`. "
            "(ROUTINE) (@lane: edc/editeur) (@after: EDC2)")
    PLAN = (
        "## BUILD QUEUE\n\n"
        "## Groupe AFAC — audit facturation du 2026-10-08\n### AFAC — M2\n"
        + AFAC17 + "\n"
        "## Groupe APRF — audit performance du 2026-10-08\n### APRF — M2\n"
        + APRF23 + "\n"
        "## Groupe EDC — éditeur de devis (écran pur, 09/10/2026)\n"
        "### EDC — M2\n"
        + EDC2 + "\n" + EDC3 + "\n"
    )

    def setUp(self):
        self.plan = Path(tempfile.mkdtemp()) / "PLAN_AUDIT_TRANSVERSE.md"
        self.plan.write_text(self.PLAN, encoding="utf-8")
        self.addCleanup(lambda: self.plan.unlink(missing_ok=True))
        # Pas de BUILD_ORDER.yml : SCA3 est un no-op, le test ne parle que
        # de la portée et de PACT11.
        self.sans_build_order = str(Path(tempfile.mktemp(suffix=".yml")))

    def _main(self, *options) -> tuple[int, str, str]:
        sortie, journal = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(journal):
            code = pl.main([str(self.plan), "--build-order",
                            self.sans_build_order, *options])
        return code, sortie.getvalue(), journal.getvalue()

    def _json(self, *options) -> dict:
        code, sortie, _ = self._main("--json", *options)
        self.assertEqual(code, 0)
        return json.loads(sortie)

    # --- le témoin : sans option, le refus d'origine est inchangé ---------
    def test_sans_portee_le_groupe_EDC_est_refuse_par_PACT11_comme_avant(self):
        plan = self._json()
        self.assertEqual(sorted(t["id"] for t in plan["pairing_blocked"]),
                         ["EDC2", "EDC3"])
        self.assertNotIn("scope", plan)
        motif = " ".join(plan["pairing_blocked"][0]["pairing_block_reasons"])
        self.assertIn("AFAC17", motif)
        self.assertIn("apps/ventes/urls.py ou selectors.py", motif)

    def test_sans_portee_le_rendu_n_a_pas_de_ligne_Portee(self):
        _, sortie, journal = self._main()
        self.assertNotIn("Portée", sortie)
        self.assertNotIn("Portée", journal)
        self.assertIn("(PACT11)", sortie)

    def test_restreindre_portee_sans_selecteur_rend_la_liste_intacte(self):
        tasks = pl.parse_tasks(self.plan)
        retenues, libelle = pl.restreindre_portee(tasks)
        self.assertIs(retenues, tasks)
        self.assertIsNone(libelle)
        retenues, libelle = pl.restreindre_portee(tasks, only=[], group=[""])
        self.assertIs(retenues, tasks)
        self.assertIsNone(libelle)

    # --- la portée : le backend hors portée n'est plus « le même run » ----
    def test_only_prefixe_EDC_aucun_refus_PACT11(self):
        plan = self._json("--only", "EDC")
        self.assertEqual(plan["pairing_blocked"], [])
        self.assertEqual(plan["counts"]["pairing_blocked"], 0)
        self.assertEqual(plan["lanes"], {"edc/editeur": ["EDC2", "EDC3"]})
        self.assertEqual(plan["scope"], {
            "selectors": "--only EDC", "retained": 2, "total": 4, "excluded": 2,
        })

    def test_only_identifiants_exacts(self):
        plan = self._json("--only", "EDC2,EDC3")
        self.assertEqual(plan["pairing_blocked"], [])
        self.assertEqual(plan["lanes"], {"edc/editeur": ["EDC2", "EDC3"]})
        plan = self._json("--only", "EDC3")
        self.assertEqual(plan["lanes"], {"edc/editeur": ["EDC3"]})
        self.assertEqual(plan["scope"]["retained"], 1)

    def test_only_repetable_est_une_union_et_ignore_la_casse(self):
        # Les deux sont RETENUES (union) ; APRF23 étant le backend ventes et
        # dans la portée, EDC2 reste appariée contre elle — c'est PACT11 qui
        # parle ensuite, pas la portée.
        plan = self._json("--only", "edc2", "--only", "aprf23")
        self.assertEqual(plan["scope"]["retained"], 2)
        self.assertEqual(plan["lanes"], {"aprf-crm/selecteurs": ["APRF23"]})
        self.assertEqual([t["id"] for t in plan["pairing_blocked"]], ["EDC2"])

    def test_group_sous_chaine_du_titre_de_groupe_ou_du_lot(self):
        # Titre `##` (« Groupe EDC — … ») ET titre `###` (« EDC — M2 »),
        # casse ignorée : les deux niveaux de la chaîne sont consultés.
        for titre in ("Groupe EDC", "groupe edc", "EDC — M2", "écran pur"):
            plan = self._json("--group", titre)
            self.assertEqual(plan["pairing_blocked"], [], titre)
            self.assertEqual(plan["lanes"], {"edc/editeur": ["EDC2", "EDC3"]},
                             titre)
        self.assertEqual(plan["scope"]["selectors"], "--group 'écran pur'")

    def test_la_portee_est_affichee_en_tete_du_rendu(self):
        code, sortie, journal = self._main("--only", "EDC")
        self.assertEqual(code, 0)
        lignes = sortie.splitlines()
        self.assertTrue(lignes[0].startswith("# Lane plan for "))
        self.assertEqual(
            lignes[1],
            "Portée : --only EDC — 2 tâche(s) ouverte(s) retenue(s) sur 4 "
            "(2 hors portée, invisibles aux portes SCA3 / PACT11 / @after externe)",
        )
        self.assertNotIn("## Refusé — moitié frontend", sortie)
        self.assertNotIn("REFUSÉ", journal)

    def test_une_tache_EN_portee_reste_refusee_pour_les_memes_motifs(self):
        # La portée n'affaiblit pas PACT11 : si la moitié backend est DANS la
        # portée, le refus est identique à l'appel sans option.
        plan = self._json("--only", "EDC,AFAC17")
        self.assertEqual(sorted(t["id"] for t in plan["pairing_blocked"]),
                         ["EDC2", "EDC3"])
        motif = " ".join(plan["pairing_blocked"][0]["pairing_block_reasons"])
        self.assertIn("AFAC17", motif)
        self.assertNotIn("APRF23", motif)       # hors portée : n'apparie rien

    def test_force_wave_garde_sa_semantique_avec_la_portee(self):
        plan = self._json("--only", "EDC,AFAC17", "--force-wave")
        self.assertEqual(plan["pairing_blocked"], [])
        self.assertEqual(sorted(sum(plan["lanes"].values(), [])),
                         ["AFAC17", "EDC2", "EDC3"])

    def test_portee_vide_avertit_sur_stderr_et_rend_un_plan_vide(self):
        code, sortie, journal = self._main("--only", "EDK")
        self.assertEqual(code, 0)
        self.assertIn("Portée vide", journal)
        self.assertIn("--only EDK", journal)
        self.assertIn("0 buildable task(s)", sortie)

    def test_SCA3_n_evalue_que_la_portee(self):
        # Le même BUILD_ORDER.yml refuse ARC3 et NTPLT1 sans portée ; avec
        # `--only ARC1`, ils ne sont plus dans le run : aucun refus émis.
        plan_path = Path(tempfile.mkdtemp()) / "PLAN.md"
        plan_path.write_text(SIMPLE_PLAN_FIXTURE, encoding="utf-8")
        self.addCleanup(lambda: plan_path.unlink(missing_ok=True))
        bo = Path(tempfile.mkdtemp()) / "BUILD_ORDER.yml"
        bo.write_text(MINI_YAML_FIXTURE, encoding="utf-8")
        self.addCleanup(lambda: bo.unlink(missing_ok=True))
        sortie, journal = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(journal):
            code = pl.main([str(plan_path), "--build-order", str(bo),
                            "--json", "--only", "ARC1"])
        self.assertEqual(code, 0)
        plan = json.loads(sortie.getvalue())
        self.assertEqual(plan["wave_blocked"], [])
        self.assertEqual(plan["lanes"], {"backend/core": ["ARC1"]})
        self.assertNotIn("REFUSÉ (ordre de vague)", journal.getvalue())

    def test_titres_par_tache_donne_la_chaine_des_titres(self):
        titres = pl.titres_par_tache(self.plan)
        self.assertEqual(
            titres["EDC2"],
            ("Groupe EDC — éditeur de devis (écran pur, 09/10/2026)",
             "EDC — M2"),
        )
        self.assertEqual(titres["AFAC17"][1], "AFAC — M2")


class Pact11Tests(unittest.TestCase):
    """AMET95 (F1, C-AMET-024) — PACT11 ne compte plus comme producteur une
    tâche que la porte `@after` externe refusera : `main()` fait un dry-run de
    cette porte d'abord et passe ses refus à
    ``apply_contract_pairing_gate(exclus=…)``. Le dépendant d'une tâche
    refusée par PACT11 reste refusé (passe transitive conservée)."""

    POOL = (
        "## BUILD QUEUE\n\n"
        # Producteur `ao` qui attend une tâche OUVERTE d'un autre plan.
        "- [ ] PB1 — routes AO. Files: `backend/django_core/apps/ao/urls.py`. "
        "(ROUTINE) (@lane: pb1) (@after: XEXT1)\n"
        "- [ ] PF1 — écran AO. Files: `frontend/src/features/ao/Ecran.jsx`. "
        "(ROUTINE) (@lane: pf1)\n"
        # Producteur `ventes` constructible : son écran reste refusé.
        "- [ ] PB2 — agrégats ventes. "
        "Files: `backend/django_core/apps/ventes/selectors.py`. "
        "(ROUTINE) (@lane: pb2)\n"
        "- [ ] PF2 — écran ventes. "
        "Files: `frontend/src/features/ventes/Ecran.jsx`. (ROUTINE) (@lane: pf2)\n"
        "- [ ] PD2 — suite de l'écran ventes. "
        "Files: `backend/django_core/apps/sav/models.py`. "
        "(ROUTINE) (@lane: pd2) (@after: PF2)\n"
    )

    def setUp(self):
        racine = Path(tempfile.mkdtemp())
        (racine / "docs" / "plans").mkdir(parents=True)
        self.pool = racine / "docs" / "plans" / "PLAN_POOL.md"
        self.pool.write_text(self.POOL, encoding="utf-8")
        (racine / "docs" / "plans" / "PLAN_AUTRE.md").write_text(
            "## BUILD QUEUE\n\n- [ ] XEXT1 — préalable ouvert. (ROUTINE)\n",
            encoding="utf-8")
        origine = pl.index_taches_plans
        pl.index_taches_plans = lambda racine_=racine: origine(racine_)
        self.addCleanup(setattr, pl, "index_taches_plans", origine)

    def _plan(self) -> dict:
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), \
                contextlib.redirect_stderr(io.StringIO()):
            code = pl.main([str(self.pool), "--json", "--build-order",
                            str(Path(tempfile.mktemp(suffix=".yml")))])
        self.assertEqual(code, 0)
        return json.loads(sortie.getvalue())

    def test_producteur_refuse_par_after_externe_exclu_de_pact11(self):
        plan = self._plan()
        apparies = {t["id"] for t in plan["pairing_blocked"]}
        apres = {t["id"] for t in plan["after_blocked"]}
        construites = {tid for ids in plan["lanes"].values() for tid in ids}
        # PB1 ne part pas (XEXT1 ouverte) : il ne produit rien dans ce run,
        # donc PF1 n'est plus refusée par PACT11 pour lui.
        self.assertIn("PB1", apres)
        self.assertNotIn("PF1", apparies)
        self.assertIn("PF1", construites)
        # PB2 part : PF2 reste refusée, et PD2 (@after PF2) ne fuit pas.
        self.assertIn("PF2", apparies)
        self.assertIn("PD2", apres)
        self.assertNotIn("PD2", construites)

    def test_tache_atomique_exemptee_de_pact11(self):
        # AMET96 : un déplacement multi-propriétaires `(@atomique: …)` se
        # construit en UN commit — PACT11 ne le refuse pas comme un écran.
        self.pool.write_text(self.POOL.replace(
            "(@lane: pf2)", "(@lane: pf2) (@atomique: devis, generateur)"),
            encoding="utf-8")
        taches = pl.parse_tasks(self.pool)
        _, refusees = pl.apply_contract_pairing_gate(taches)
        self.assertEqual({t["id"] for t in refusees}, {"PF1"})
        pf2 = next(t for t in taches if t["id"] == "PF2")
        self.assertEqual(pf2["atomique"], ["devis", "generateur"])
        self.assertNotIn("atomique", taches[0])  # sans tag : dict inchangé


if __name__ == "__main__":
    unittest.main()
