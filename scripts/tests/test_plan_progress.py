"""Tests SCA2 — scripts/plan_progress.py.

Pure stdlib (unittest), no Django/DB needed. Run with:
    python -m unittest scripts.tests.test_plan_progress -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import plan_progress as pp  # noqa: E402


CHECKBOX_FIXTURE = """\
## BUILD QUEUE

- [ ] ARC1 — First kernel task. Files: `core/models.py`.
- [x] ARC2 — Second kernel task, already done.
- [ ] ARC3 — Third kernel task.
- [BLOCKED: needs founder secret] ARC4 — Fourth, blocked (counts as open).
- [ ] SCA1 — Unrelated prefix task.
"""

HEADER_FIXTURE = """\
### T1 — Bulk actions on leads — [x]
some body text here, not a task line
### T2 — Another header task — [ ]
more body text
"""

COMPOUND_FIXTURE = """\
## Lane frontend/flotte

- [ ] FE-XFLT4 — single id compound task. (@lane: frontend/flotte)
- [x] FE-XFLT1-3 — range-suffixed compound task, done.
- [ ] FE-XFLT7/15/18 — multi-id-list compound task.
- [ ] FE-XFAC14/XACC26 — compound with a DIFFERENT trailing prefix suffix.
"""

BOLD_ID_FIXTURE = """\
- [ ] **NTIDE1** — bold-wrapped id, open.
- [x] **NTIDE2** — bold-wrapped id, done.
"""


class PlanProgressTests(unittest.TestCase):
    def _write(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_checkbox_format_counts_done_and_open(self):
        path = self._write(CHECKBOX_FIXTURE)
        counts = pp.count_file(path)
        self.assertEqual(counts["ARC"], {"done": 1, "total": 4})
        self.assertEqual(counts["SCA"], {"done": 0, "total": 1})

    def test_blocked_status_counts_as_open_not_done(self):
        path = self._write(CHECKBOX_FIXTURE)
        counts = pp.count_file(path)
        # ARC4 is [BLOCKED: ...] -> open, included in total (4), not done (1).
        self.assertEqual(counts["ARC"]["total"], 4)
        self.assertEqual(counts["ARC"]["done"], 1)

    def test_header_format_counts_done_and_open(self):
        path = self._write(HEADER_FIXTURE)
        counts = pp.count_file(path)
        self.assertEqual(counts["T"], {"done": 1, "total": 2})

    def test_compound_prefix_counts_one_task_per_line(self):
        path = self._write(COMPOUND_FIXTURE)
        counts = pp.count_file(path)
        # 4 checkbox lines under FE-XFLT/FE-XFAC compound ids: FE-XFLT has 3
        # lines (FE-XFLT4, FE-XFLT1-3, FE-XFLT7/15/18), FE-XFAC has 1
        # (FE-XFAC14/XACC26 collapses to prefix FE-XFAC, not FE-XACC).
        self.assertEqual(counts["FE-XFLT"], {"done": 1, "total": 3})
        self.assertEqual(counts["FE-XFAC"], {"done": 0, "total": 1})
        self.assertNotIn("FE-XACC", counts)

    def test_bold_wrapped_id_is_recognised(self):
        path = self._write(BOLD_ID_FIXTURE)
        counts = pp.count_file(path)
        self.assertEqual(counts["NTIDE"], {"done": 1, "total": 2})

    def test_missing_file_returns_empty_without_error(self):
        counts = pp.count_file(Path("this/file/does/not/exist.md"))
        self.assertEqual(counts, {})

    def test_aggregate_sums_across_files(self):
        p1 = self._write(CHECKBOX_FIXTURE)
        p2 = self._write("- [x] ARC9 — another file, done.\n")
        agg = pp.aggregate([p1, p2])
        self.assertEqual(agg["ARC"], {"done": 2, "total": 5})

    def test_with_pct_computes_percentage(self):
        counts = {"ARC": {"done": 1, "total": 4}}
        out = pp.with_pct(counts)
        self.assertEqual(out["ARC"]["pct"], 25.0)

    def test_with_pct_zero_total_is_zero_pct_no_division_error(self):
        counts = {"EMPTY": {"done": 0, "total": 0}}
        out = pp.with_pct(counts)
        self.assertEqual(out["EMPTY"]["pct"], 0.0)

    def test_group_pct_unknown_prefix_is_zero(self):
        p1 = self._write(CHECKBOX_FIXTURE)
        self.assertEqual(pp.group_pct("NOPE", [p1]), 0.0)

    def test_main_prints_stable_json(self):
        import io
        import contextlib
        import json

        p1 = self._write(CHECKBOX_FIXTURE)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = pp.main(["--files", str(p1), "--compact"])
        self.assertEqual(exit_code, 0)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["ARC"], {"done": 1, "total": 4, "pct": 25.0})

    def test_main_single_prefix_filter(self):
        import io
        import contextlib
        import json

        p1 = self._write(CHECKBOX_FIXTURE)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pp.main(["--files", str(p1), "--compact", "--prefix", "SCA"])
        data = json.loads(buf.getvalue())
        self.assertEqual(list(data.keys()), ["SCA"])

    def test_real_repo_state_is_parseable_and_nonempty(self):
        """Smoke test against the REAL plan files (proves the script runs
        clean on actual repo state, not just fixtures)."""
        data = pp.progress()
        self.assertIn("ARC", data)
        self.assertGreater(data["ARC"]["total"], 0)
        self.assertIn("SCA", data)
        self.assertGreaterEqual(data["SCA"]["total"], 45)


if __name__ == "__main__":
    unittest.main()
