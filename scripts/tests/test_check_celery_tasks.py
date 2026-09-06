"""Tests YDATA14 / AUD828 (M-09) -- scripts/check_celery_tasks.py.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_celery_tasks -v

AUD828 ROUGE d'abord: before the fix, file discovery was a CLOSED SET of 3
literal filenames (tasks.py/scheduled.py/beat_tasks.py) -- a real
@shared_task in any other module (core/jobs.py, apps/x/sweeps.py,
apps/x/foo_tasks.py...) was never even opened. The fix switches to
CONTENT-based discovery (any .py file mentioning the decorator token, with
check_file()'s AST walk as the real detector) across apps/*, core and
authentication, excluding tests/migrations.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_celery_tasks as cct  # noqa: E402


INSTANCE_PARAM_TASK = '''
from celery import shared_task


@shared_task
def envoyer_relance(devis):
    devis.save()
'''

PK_PARAM_TASK_OK = '''
from celery import shared_task


@shared_task
def envoyer_relance(devis_id):
    pass
'''

NOT_A_TASK = '''
def devis(x):
    return x
'''


class TestDetection(unittest.TestCase):
    def _codes(self, src):
        # _rel() in this module (unlike sibling guards) has no try/except
        # around relative_to(ROOT) -- keep the fixture INSIDE the repo.
        with tempfile.NamedTemporaryFile(
                "w", suffix=".py", delete=False, encoding="utf-8",
                dir=ROOT / "scripts" / "tests") as fh:
            fh.write(src)
            path = Path(fh.name)
        try:
            _rows, findings = cct.check_file(path)
            return {code for code, _msg in findings}
        finally:
            path.unlink()

    def test_instance_like_param_flagged(self):
        self.assertIn(
            "TASK_TAKES_MODEL_INSTANCE", self._codes(INSTANCE_PARAM_TASK))

    def test_pk_suffixed_param_ok(self):
        self.assertEqual(self._codes(PK_PARAM_TASK_OK), set())

    def test_undecorated_function_ignored(self):
        self.assertEqual(self._codes(NOT_A_TASK), set())


class TestSurfaceEnumeration(unittest.TestCase):
    """AUD828 (M-09) -- ROUGE d'abord: a @shared_task in an arbitrarily-
    named module (not tasks.py/scheduled.py/beat_tasks.py) must now be
    discovered; tests/ and migrations/ subtrees must stay excluded."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests")
        self.addCleanup(self._tmp.cleanup)
        self.apps_dir = Path(self._tmp.name) / "apps"
        self.core_dir = Path(self._tmp.name) / "core"
        self.auth_dir = Path(self._tmp.name) / "authentication"
        for d in (self.apps_dir, self.core_dir, self.auth_dir):
            d.mkdir(parents=True)
        self.app_dir = self.apps_dir / "demo"
        self.app_dir.mkdir()

        self._orig = (cct.APPS_DIR, cct.CORE_DIR, cct.AUTH_DIR)
        cct.APPS_DIR = self.apps_dir
        cct.CORE_DIR = self.core_dir
        cct.AUTH_DIR = self.auth_dir
        self.addCleanup(self._restore)

    def _restore(self):
        cct.APPS_DIR, cct.CORE_DIR, cct.AUTH_DIR = self._orig

    def test_arbitrarily_named_module_with_shared_task_opened(self):
        f = self.app_dir / "sweeps.py"
        f.write_text(INSTANCE_PARAM_TASK, encoding="utf-8")
        self.assertIn(f, list(cct._iter_task_files()))

    def test_core_jobs_module_opened(self):
        f = self.core_dir / "jobs.py"
        f.write_text(INSTANCE_PARAM_TASK, encoding="utf-8")
        self.assertIn(f, list(cct._iter_task_files()))

    def test_authentication_tasks_module_opened(self):
        f = self.auth_dir / "tasks.py"
        f.write_text(INSTANCE_PARAM_TASK, encoding="utf-8")
        self.assertIn(f, list(cct._iter_task_files()))

    def test_file_without_task_token_not_opened(self):
        f = self.app_dir / "helpers.py"
        f.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.assertNotIn(f, list(cct._iter_task_files()))

    def test_tests_subtree_excluded(self):
        tests_dir = self.app_dir / "tests"
        tests_dir.mkdir()
        f = tests_dir / "test_fixture_tasks.py"
        f.write_text(INSTANCE_PARAM_TASK, encoding="utf-8")
        self.assertNotIn(f, list(cct._iter_task_files()))

    def test_migrations_subtree_excluded(self):
        mig_dir = self.app_dir / "migrations"
        mig_dir.mkdir()
        f = mig_dir / "0001_initial.py"
        f.write_text(INSTANCE_PARAM_TASK, encoding="utf-8")
        self.assertNotIn(f, list(cct._iter_task_files()))


if __name__ == "__main__":
    unittest.main()
