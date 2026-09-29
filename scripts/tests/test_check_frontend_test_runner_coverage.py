"""Tests de scripts/check_frontend_test_runner_coverage.py
(ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES, 28/09/2026).

Stdlib pur (unittest), aucune base de donnees, aucun Django, aucun node.
Lancer :
    python -m unittest scripts.tests.test_check_frontend_test_runner_coverage -v

Le test qui compte est le NEGATIF EXECUTE : un fichier *.test.<suffixe
inconnu> sous frontend/src doit rougir la garde en le nommant. Une garde
qu'on n'a jamais vue rougir ne prouve rien.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_frontend_test_runner_coverage as guard  # noqa: E402


class NodeTestGlobParsingTests(unittest.TestCase):
    def test_reads_the_real_ci_yml_glob(self):
        """Read straight from the repo's own ci.yml — proves the guard tracks
        the REAL `node --test` invocation, not a hand-copied literal."""
        suffixes = guard.node_test_suffixes()
        self.assertIn("mjs", suffixes)

    def test_missing_or_unmatched_file_yields_empty_set(self):
        self.assertEqual(guard.node_test_suffixes("/nonexistent/ci.yml"), set())

    def test_parses_an_arbitrary_glob_from_a_fake_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = os.path.join(tmp, "ci.yml")
            with open(fake, "w", encoding="utf-8") as fh:
                fh.write('run: node --test "src/**/*.test.cjs"\n')
            self.assertEqual(guard.node_test_suffixes(fake), {"cjs"})


class VitestSuffixTests(unittest.TestCase):
    def test_matches_the_sharders_own_constant(self):
        """No re-derivation: the two must be the literal same set, always."""
        fs = guard._import_ci_frontend_shard()
        expected = {s.rsplit(".", 1)[-1] for s in fs.INCLUDE_SUFFIXES}
        self.assertEqual(guard.vitest_suffixes(), expected)
        self.assertIn("jsx", expected)
        self.assertIn("js", expected)


class OrphanDetectionTests(unittest.TestCase):
    """Builds a throwaway frontend/src tree so the RED case is actually
    exercised, not just asserted about the real repo (which should be green
    today)."""

    def _make_tree(self, files):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        frontend = os.path.join(tmp.name, "frontend")
        src = os.path.join(frontend, "src")
        os.makedirs(src, exist_ok=True)
        for rel in files:
            full = os.path.join(src, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as fh:
                fh.write("// fixture\n")
        return frontend

    def test_a_covered_suffix_is_not_flagged(self):
        frontend = self._make_tree(["ui/Widget.test.jsx", "lib/util.test.js"])
        orphans, _covered = guard.find_orphans(frontend)
        self.assertEqual(orphans, [])

    def test_an_uncovered_suffix_is_flagged_by_name(self):
        """The RED case: a *.test.ts file (no runner picks up .ts today)."""
        frontend = self._make_tree(["ui/Widget.test.jsx", "lib/legacy.test.ts"])
        orphans, _covered = guard.find_orphans(frontend)
        self.assertEqual(orphans, [("src/lib/legacy.test.ts", "ts")])

    def test_non_test_files_are_ignored(self):
        frontend = self._make_tree(["ui/Widget.jsx", "lib/helpers.js"])
        orphans, _covered = guard.find_orphans(frontend)
        self.assertEqual(orphans, [])

    def test_main_exits_nonzero_and_names_the_orphan(self):
        frontend = self._make_tree(["lib/legacy.test.ts"])
        real_src = guard.SRC_DIR
        real_frontend = guard.FRONTEND
        guard.SRC_DIR = os.path.join(frontend, "src")
        guard.FRONTEND = frontend
        try:
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = guard.main([])
            self.assertEqual(rc, 1)
            self.assertIn("legacy.test.ts", buf.getvalue())
        finally:
            guard.SRC_DIR = real_src
            guard.FRONTEND = real_frontend


class RealRepoTests(unittest.TestCase):
    """The guard against the ACTUAL repo tree must be green — this is the
    regression it exists to catch (ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES)."""

    def test_the_real_repo_has_zero_orphans_today(self):
        orphans, covered = guard.find_orphans()
        self.assertEqual(orphans, [], f"orphelin(s) detecte(s) : {orphans}")
        self.assertIn("jsx", covered)
        self.assertIn("js", covered)
        self.assertIn("mjs", covered)

    def test_main_is_green_on_the_real_repo(self):
        self.assertEqual(guard.main([]), 0)


if __name__ == "__main__":
    unittest.main()
