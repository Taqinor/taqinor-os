"""Tests NTPLT21 / AUD831 -- scripts/check_query_budgets.py.

Pure stdlib (unittest) + PyYAML (a hard dependency of the script once
branched into CI, per AUD831). Run:
    python -m unittest scripts.tests.test_check_query_budgets -v

AUD831 ROUGE d'abord: before this task, check_query_budgets.py was never
invoked by any CI job (`grep -rn query_budgets .github/` rendered 0
occurrence) — an endpoint declared `enforced: true` with NO budget test
never made a single job red. The SCRIPT's own detection logic already
worked correctly in isolation; what was missing was the wiring (now in
ci.yml's stage-names job) and a hard failure on a missing PyYAML (used to
silently exit 0 — see test_missing_pyyaml_now_fails_loud below).
"""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_query_budgets as cqb  # noqa: E402


class _Harness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests")
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.backend = self.tmp_path / "backend" / "django_core"
        self.backend.mkdir(parents=True)
        self.manifest = self.tmp_path / "query-budgets.yml"

        self._orig = (cqb.MANIFEST, cqb.BACKEND)
        cqb.MANIFEST = self.manifest
        cqb.BACKEND = self.backend
        self.addCleanup(self._restore)

    def _restore(self):
        cqb.MANIFEST, cqb.BACKEND = self._orig

    def _write_manifest(self, text):
        self.manifest.write_text(textwrap.dedent(text), encoding="utf-8")

    def _write_test_file(self, name, text):
        f = self.backend / name
        f.write_text(textwrap.dedent(text), encoding="utf-8")
        return f


ENFORCED_ENDPOINT = """\
    version: 1
    endpoints:
      - path: /api/django/crm/leads/
        budget: 12
        enforced: true
        note: "test"
"""


class TestManifestAbsent(_Harness):
    def test_missing_manifest_is_ok(self):
        self.assertFalse(self.manifest.exists())
        self.assertEqual(cqb.main(), 0)


class TestRougeDabordEnforcedWithoutTest(_Harness):
    """AUD831 Done= -- the exact scenario named in the task: an endpoint
    'enforced: true' with NO budget test."""

    def test_enforced_endpoint_without_budget_test_fails(self):
        self._write_manifest(ENFORCED_ENDPOINT)
        # No test file at all -> the endpoint has zero coverage.
        self.assertEqual(cqb.main(), 1)

    def test_enforced_endpoint_with_budget_test_passes(self):
        self._write_manifest(ENFORCED_ENDPOINT)
        self._write_test_file("test_leads_budget.py", """\
            class T:
                def test_budget(self):
                    with self.assertMaxQueries(12):
                        self.client.get('/api/django/crm/leads/')
        """)
        self.assertEqual(cqb.main(), 0)

    def test_enforced_endpoint_whose_test_was_removed_fails(self):
        """The second half of the scenario: an ALREADY-enforced endpoint
        whose test disappears in a refactor must be caught too."""
        self._write_manifest(ENFORCED_ENDPOINT)
        f = self._write_test_file("test_leads_budget.py", """\
            class T:
                def test_budget(self):
                    with self.assertMaxQueries(12):
                        self.client.get('/api/django/crm/leads/')
        """)
        self.assertEqual(cqb.main(), 0)
        f.unlink()
        self.assertEqual(cqb.main(), 1)

    def test_not_enforced_endpoint_without_test_is_ok(self):
        self._write_manifest("""\
            version: 1
            endpoints:
              - path: /api/django/ventes/factures/
                budget: 15
                enforced: false
                note: "pas encore couvert"
        """)
        self.assertEqual(cqb.main(), 0)

    def test_assert_num_queries_also_counts(self):
        self._write_manifest(ENFORCED_ENDPOINT)
        self._write_test_file("test_leads_budget.py", """\
            class T:
                def test_budget(self):
                    with self.assertNumQueries(12):
                        self.client.get('/api/django/crm/leads/')
        """)
        self.assertEqual(cqb.main(), 0)


class TestMalformedManifest(_Harness):
    def test_endpoints_not_a_list_fails(self):
        self._write_manifest("endpoints: 'not a list'\n")
        self.assertEqual(cqb.main(), 1)

    def test_non_dict_entry_fails(self):
        self._write_manifest("endpoints:\n  - 'just a string'\n")
        self.assertEqual(cqb.main(), 1)

    def test_enforced_without_path_fails(self):
        self._write_manifest("endpoints:\n  - enforced: true\n")
        self.assertEqual(cqb.main(), 1)

    def test_unreadable_yaml_fails(self):
        self._write_manifest("endpoints: [unterminated\n")
        self.assertEqual(cqb.main(), 1)


class TestMissingPyYAML(_Harness):
    """AUD831 — the behavioural change: PyYAML absent used to be a silent
    exit 0 ('dependance dev'); once this guard is wired into CI (which
    installs PyYAML), a missing PyYAML there is an environment regression,
    not a legitimate case — it must fail loud."""

    def test_missing_pyyaml_now_fails_loud(self):
        self._write_manifest(ENFORCED_ENDPOINT)
        orig_import = __import__

        def _blocked_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("simulated: PyYAML not installed")
            return orig_import(name, *args, **kwargs)

        import builtins
        real_builtin_import = builtins.__import__
        builtins.__import__ = _blocked_import
        try:
            self.assertEqual(cqb.main(), 1)
        finally:
            builtins.__import__ = real_builtin_import


if __name__ == "__main__":
    unittest.main()
