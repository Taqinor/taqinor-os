"""Tests — scripts/ci_testdb_manifest_diff.py (the WOW8 testdb-cache safety guard).

This guard gates every merge: if it wrongly says DELTA, a stale schema passes CI
green. Pure stdlib (unittest), no Django/DB needed. Run with:
    python -m unittest scripts.tests.test_ci_testdb_manifest_diff -v
"""
import io
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ci_testdb_manifest_diff as guard  # noqa: E402


def h(seed):
    """A deterministic, well-formed 64-hex content hash."""
    return "{0:064x}".format(seed)


def manifest(*pairs):
    """Build sha256sum-style text: manifest((hash, path), ...)."""
    return "".join("{0}  ./{1}\n".format(digest, path) for digest, path in pairs)


def run(old_text, cur_text):
    """Run the decision over two manifest bodies -> (exit_code, report_text)."""
    with tempfile.TemporaryDirectory() as tmp:
        old_path = os.path.join(tmp, "old.manifest")
        cur_path = os.path.join(tmp, "cur.manifest")
        for path, text in ((old_path, old_text), (cur_path, cur_text)):
            if text is not None:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(text)
        buf = io.StringIO()
        stdout = sys.stdout
        sys.stdout = buf
        try:
            code = guard.main([old_path, cur_path])
        finally:
            sys.stdout = stdout
        return code, buf.getvalue()


V = "apps/ventes/migrations/"
C = "apps/crm/migrations/"

BASE = ((h(1), V + "0089_alter_rooflayout_devis.py"), (h(2), C + "0060_lead.py"))


class DeltaPathTests(unittest.TestCase):
    def test_identical_manifests_take_the_delta(self):
        code, out = run(manifest(*BASE), manifest(*BASE))
        self.assertEqual(code, guard.EXIT_DELTA)
        self.assertIn("VERDICT: DELTA", out)

    def test_pure_additions_take_the_delta(self):
        cur = manifest(*(BASE + ((h(3), V + "0090_ydata2.py"), (h(4), C + "0061_new.py"))))
        code, out = run(manifest(*BASE), cur)
        self.assertEqual(code, guard.EXIT_DELTA)
        self.assertIn("VERDICT: DELTA", out)
        self.assertIn("2 new migration file(s)", out)
        self.assertIn("0090_ydata2.py", out)

    def test_binary_mode_sha256sum_output_is_accepted(self):
        # GNU sha256sum: "<hash>  <path>" (text, ubuntu runner) vs "<hash> *<path>"
        # (binary, Git-for-Windows). Rejecting either would silently degrade every
        # run to a ~70-minute rebuild.
        binary = "".join("{0} *./{1}\n".format(d, p) for d, p in BASE)
        code, out = run(binary, manifest(*BASE))
        self.assertEqual(code, guard.EXIT_DELTA, out)
        code, out = run(binary, binary)
        self.assertEqual(code, guard.EXIT_DELTA, out)

    def test_text_mode_path_starting_with_a_star_is_not_mangled(self):
        mapping, error = guard.parse_manifest("{0}  *odd.py\n".format(h(1)))
        self.assertIsNone(error)
        self.assertEqual(list(mapping), ["*odd.py"])

    def test_path_prefix_and_ordering_do_not_matter(self):
        # `find .` emits "./apps/..."; a manifest written without the "./" or in a
        # different order must decide identically (no spurious rebuild).
        cur = "".join("{0}  {1}\n".format(d, p) for d, p in reversed(BASE))
        code, _ = run(manifest(*BASE), cur)
        self.assertEqual(code, guard.EXIT_DELTA)


class RebuildPathTests(unittest.TestCase):
    def test_edit_in_place_is_detected_and_forces_a_rebuild(self):
        cur = manifest((h(99), V + "0089_alter_rooflayout_devis.py"), BASE[1])
        code, out = run(manifest(*BASE), cur)
        self.assertEqual(code, guard.EXIT_REBUILD)
        self.assertIn("VERDICT: REBUILD", out)
        self.assertIn("EDITED-IN-PLACE", out)
        self.assertIn("0089_alter_rooflayout_devis.py", out)

    def test_deletion_is_detected_and_forces_a_rebuild(self):
        code, out = run(manifest(*BASE), manifest(BASE[1]))
        self.assertEqual(code, guard.EXIT_REBUILD)
        self.assertIn("DELETED", out)
        self.assertIn("0089_alter_rooflayout_devis.py", out)

    def test_byte_identical_rename_is_detected_and_still_rebuilds(self):
        # Same content hash at a new path = a pure rename. It is REPORTED as such
        # (so the log explains itself) but deliberately NOT given a fast path.
        cur = manifest((h(1), V + "0091_alter_rooflayout_devis.py"), BASE[1])
        code, out = run(manifest(*BASE), cur)
        self.assertEqual(code, guard.EXIT_REBUILD)
        self.assertIn("RENAMED", out)
        self.assertIn("-> apps/ventes/migrations/0091_alter_rooflayout_devis.py", out)

    def test_renumber_with_rewritten_dependencies_is_reported_as_an_edit(self):
        # The real repo pattern (17/17 renames): renumbered AND content changed,
        # because `dependencies` was re-chained behind the colliding migration.
        # It must NOT be mistaken for a safe rename.
        old = manifest((h(1), V + "0090_protect_produit.py"))
        cur = manifest(
            (h(50), V + "0090_ydata2_protect_dossier.py"),
            (h(51), V + "0091_protect_produit.py"),
        )
        code, out = run(old, cur)
        self.assertEqual(code, guard.EXIT_REBUILD)
        self.assertIn("RENUMBERED+EDITED", out)
        self.assertIn("-> apps/ventes/migrations/0091_protect_produit.py", out)
        self.assertNotIn("RENAMED ", out)

    def test_a_rename_across_apps_is_never_claimed_as_a_renumber(self):
        # Same stem, different app: no same-app candidate, so it degrades to
        # DELETED rather than pretending to understand the move.
        old = manifest((h(1), V + "0090_protect_produit.py"))
        cur = manifest((h(52), C + "0090_protect_produit.py"))
        code, out = run(old, cur)
        self.assertEqual(code, guard.EXIT_REBUILD)
        self.assertIn("DELETED", out)

    def test_a_removed_dunder_init_is_never_claimed_as_a_rename(self):
        # Empty __init__.py files all share one content hash across every app, so
        # matching them by content would invent bogus renames. They are not
        # migrations and are only ever reported as DELETED/EDITED.
        old = manifest((h(0), V + "__init__.py"))
        cur = manifest((h(0), C + "__init__.py"))
        code, out = run(old, cur)
        self.assertEqual(code, guard.EXIT_REBUILD)
        self.assertIn("DELETED", out)
        self.assertNotIn("RENAMED", out)

    def test_one_offender_among_many_unchanged_files_still_rebuilds(self):
        old = manifest(*(BASE + ((h(5), V + "0090_x.py"),)))
        cur = manifest(*(BASE + ((h(6), V + "0090_x.py"), (h(7), C + "0061_new.py"))))
        code, out = run(old, cur)
        self.assertEqual(code, guard.EXIT_REBUILD)
        self.assertIn("1 migration file(s)", out)


class FailSafeTests(unittest.TestCase):
    def test_missing_manifest_file_rebuilds(self):
        code, out = run(None, manifest(*BASE))
        self.assertEqual(code, guard.EXIT_UNUSABLE)
        self.assertIn("VERDICT: REBUILD", out)

    def test_empty_manifest_rebuilds(self):
        # `comm -23` against an empty file printed nothing = "delta is safe".
        # A truncated manifest must never green-light a delta.
        code, out = run("", manifest(*BASE))
        self.assertEqual(code, guard.EXIT_UNUSABLE)
        self.assertIn("empty", out)

    def test_whitespace_only_manifest_rebuilds(self):
        code, _ = run("\n  \n\n", manifest(*BASE))
        self.assertEqual(code, guard.EXIT_UNUSABLE)

    def test_malformed_line_rebuilds(self):
        code, out = run("not-a-hash  " + V + "0089.py\n", manifest(*BASE))
        self.assertEqual(code, guard.EXIT_UNUSABLE)
        self.assertIn("not '<sha256>  <path>'", out)

    def test_truncated_hash_rebuilds(self):
        code, _ = run("abc123  " + V + "0089.py\n", manifest(*BASE))
        self.assertEqual(code, guard.EXIT_UNUSABLE)

    def test_escaped_backslash_path_rebuilds(self):
        code, _ = run("\\" + h(1) + "  " + V + "0089\\n.py\n", manifest(*BASE))
        self.assertEqual(code, guard.EXIT_UNUSABLE)

    def test_duplicate_path_rebuilds(self):
        dup = manifest((h(1), V + "0089.py"), (h(2), V + "0089.py"))
        code, out = run(dup, manifest(*BASE))
        self.assertEqual(code, guard.EXIT_UNUSABLE)
        self.assertIn("twice", out)

    def test_unusable_current_manifest_rebuilds(self):
        code, _ = run(manifest(*BASE), "garbage\n")
        self.assertEqual(code, guard.EXIT_UNUSABLE)

    def test_wrong_argument_count_rebuilds(self):
        stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            self.assertEqual(guard.main([]), guard.EXIT_UNUSABLE)
            self.assertEqual(guard.main(["a", "b", "c"]), guard.EXIT_UNUSABLE)
        finally:
            sys.stdout = stdout


class CommEquivalenceTests(unittest.TestCase):
    """The verdict must equal the `comm -23 old cur` rule this replaces.

    Oracle: rebuild iff some "<sha>  <path>" line of the old manifest is absent
    from the current one. Only well-formed inputs are compared — the malformed /
    empty cases are a deliberate tightening covered by FailSafeTests.
    """

    def test_matches_comm_semantics_on_randomised_trees(self):
        rng = random.Random(20260731)
        for case in range(300):
            paths = ["apps/a{0}/migrations/{1:04d}_m.py".format(i % 4, i) for i in range(12)]
            old = {p: h(rng.randrange(1, 40)) for p in paths if rng.random() < 0.85}
            cur = dict(old)
            for path in list(cur):
                roll = rng.random()
                if roll < 0.12:            # edited in place
                    cur[path] = h(rng.randrange(41, 80))
                elif roll < 0.24:          # renamed/renumbered (content kept or not)
                    del cur[path]
                    new = path.replace("_m.py", "_m2.py")
                    cur[new] = old[path] if rng.random() < 0.5 else h(rng.randrange(81, 120))
                elif roll < 0.30:          # deleted
                    del cur[path]
            for i in range(rng.randrange(0, 4)):  # pure additions
                cur["apps/new/migrations/{0:04d}_n.py".format(i)] = h(rng.randrange(121, 160))

            expected_rebuild = any(cur.get(p) != d for p, d in old.items())
            if not old:
                continue
            code, _ = run(
                "".join("{0}  ./{1}\n".format(d, p) for p, d in sorted(old.items())),
                "".join("{0}  ./{1}\n".format(d, p) for p, d in sorted(cur.items())) or None,
            )
            if not cur:
                self.assertEqual(code, guard.EXIT_UNUSABLE, case)
                continue
            self.assertEqual(
                code,
                guard.EXIT_REBUILD if expected_rebuild else guard.EXIT_DELTA,
                "case {0}: old={1} cur={2}".format(case, old, cur),
            )


class RealTreeSmokeTest(unittest.TestCase):
    def test_the_repos_own_migration_tree_is_a_no_op_against_itself(self):
        """A manifest of the real tree, compared with itself, must say DELTA.

        Guards against a parser that chokes on this repo's ~1400 real paths
        (which would turn every cache restore into a ~70-minute rebuild).
        """
        core = ROOT / "backend" / "django_core"
        if not core.is_dir():
            self.skipTest("backend/django_core not present")
        lines = []
        for index, path in enumerate(sorted(core.glob("*/**/migrations/*.py"))):
            rel = path.relative_to(core).as_posix()
            lines.append("{0}  ./{1}\n".format(h(index + 1), rel))
        self.assertGreater(len(lines), 100, "expected the real migration tree")
        text = "".join(lines)
        code, out = run(text, text)
        self.assertEqual(code, guard.EXIT_DELTA, out)


class CliTests(unittest.TestCase):
    def test_exit_codes_over_a_real_subprocess(self):
        """The action reads the PROCESS exit code — verify it end to end."""
        script = str(ROOT / "scripts" / "ci_testdb_manifest_diff.py")
        with tempfile.TemporaryDirectory() as tmp:
            old_path = os.path.join(tmp, "old.manifest")
            cur_path = os.path.join(tmp, "cur.manifest")
            with open(old_path, "w", encoding="utf-8") as handle:
                handle.write(manifest(*BASE))
            with open(cur_path, "w", encoding="utf-8") as handle:
                handle.write(manifest(*(BASE + ((h(9), V + "0090_new.py"),))))
            done = subprocess.run([sys.executable, script, old_path, cur_path], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertIn("VERDICT: DELTA", done.stdout)

            with open(cur_path, "w", encoding="utf-8") as handle:
                handle.write(manifest((h(77), V + "0089_alter_rooflayout_devis.py"), BASE[1]))
            done = subprocess.run([sys.executable, script, old_path, cur_path], capture_output=True, text=True)
            self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
            self.assertIn("EDITED-IN-PLACE", done.stdout)


if __name__ == "__main__":
    unittest.main()
