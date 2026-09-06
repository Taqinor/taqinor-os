"""Tests YDATA18 — scripts/check_unique_scoping.py.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_unique_scoping -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_unique_scoping as cus  # noqa: E402


def _check(src):
    with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(src)
        path = Path(fh.name)
    try:
        return cus.check_file(path)
    finally:
        path.unlink()


BARE_UNIQUE = '''
from django.db import models


class Devis(models.Model):
    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)
    reference = models.CharField(max_length=20, unique=True)
'''

COMPANY_SCOPED = '''
from django.db import models


class Devis(models.Model):
    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)
    reference = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'reference'], name='u'),
        ]
'''

GLOBAL_TOKEN = '''
from django.db import models


class ApiKey(models.Model):
    key_hash = models.CharField(max_length=64, unique=True)
    token = models.CharField(max_length=64, unique=True)
'''

SOFTDELETE_NO_CONDITION = '''
from django.db import models
from core.models import SoftDeleteModel


class Lead(SoftDeleteModel):
    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)
    ext = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['company', 'ext'], name='u'),
        ]
'''

SOFTDELETE_WITH_CONDITION = '''
from django.db import models
from django.db.models import Q
from core.models import SoftDeleteModel


class Lead(SoftDeleteModel):
    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)
    ext = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'ext'], name='u',
                condition=Q(is_deleted=False)),
        ]
'''


class TestSurfaceEnumeration(unittest.TestCase):
    """AUD828 (M-08) -- ROUGE d'abord: before the fix, a models_*.py split
    file and anything under core/authentication were NEVER OPENED (bare
    apps/*/models.py only)."""

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

        self._orig = (cus.APPS_DIR, cus.CORE_DIR, cus.AUTH_DIR)
        cus.APPS_DIR = self.apps_dir
        cus.CORE_DIR = self.core_dir
        cus.AUTH_DIR = self.auth_dir
        self.addCleanup(self._restore)

    def _restore(self):
        cus.APPS_DIR, cus.CORE_DIR, cus.AUTH_DIR = self._orig

    def test_models_split_file_opened(self):
        f = self.app_dir / "models_intervention.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertIn(f, list(cus._iter_models_files()))

    def test_core_models_file_opened(self):
        f = self.core_dir / "models.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertIn(f, list(cus._iter_models_files()))

    def test_authentication_models_file_opened(self):
        f = self.auth_dir / "models.py"
        f.write_text("class X:\n    pass\n", encoding="utf-8")
        self.assertIn(f, list(cus._iter_models_files()))


class TestUniqueScoping(unittest.TestCase):
    def _codes(self, src):
        _sites, findings = _check(src)
        return {code for code, _key, _msg in findings}

    def test_bare_business_unique_flagged(self):
        self.assertIn("UNIQUE_NOT_COMPANY_SCOPED", self._codes(BARE_UNIQUE))

    def test_company_scoped_unique_ok(self):
        self.assertEqual(self._codes(COMPANY_SCOPED), set())

    def test_global_token_names_exempt(self):
        self.assertEqual(self._codes(GLOBAL_TOKEN), set())

    def test_softdelete_unique_without_condition_flagged(self):
        self.assertIn(
            "SOFTDELETE_UNIQUE_NOT_PARTIAL",
            self._codes(SOFTDELETE_NO_CONDITION))

    def test_softdelete_unique_with_condition_ok(self):
        self.assertEqual(self._codes(SOFTDELETE_WITH_CONDITION), set())


if __name__ == "__main__":
    unittest.main()
