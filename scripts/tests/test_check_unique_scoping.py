"""Tests YDATA18 — scripts/check_unique_scoping.py.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_unique_scoping -v
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_unique_scoping as cus  # noqa: E402 — après sys.path/setup() (D-ENF22)


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

    def test_modele_deplace_garde_sa_cle_models_py(self):
        """Scission SPL : la clé gelée ``<app>/models.py::M.f`` couvre le
        modèle déplacé dans ``<app>/models_<x>.py`` — jamais une autre app,
        jamais un fichier hors ``models_*``."""
        allow = {"apps/crm/models.py::Client.code_parrainage"}
        self.assertTrue(cus._autorise(
            "apps/crm/models_clients.py::Client.code_parrainage", allow))
        self.assertFalse(cus._autorise(
            "apps/ventes/models_x.py::Client.code_parrainage", allow))
        self.assertFalse(cus._autorise(
            "apps/crm/autre.py::Client.code_parrainage", allow))


class MainTests(unittest.TestCase):
    """ATST47 (C-ATST-025) — ``main()`` joué sur un arbre fautif. Mutants
    ``if offenders:`` → ``if False:``, balayage vidé, ``if True: continue``
    ⇒ ``test_unique_non_scope_fait_sortir_un`` échoue."""

    setUp = TestSurfaceEnumeration.setUp
    _restore = TestSurfaceEnumeration._restore

    def _main(self, src, allow=""):
        (self.app_dir / "models.py").write_text(src, encoding="utf-8")
        liste = Path(self._tmp.name) / "allow.txt"
        liste.write_text(allow, encoding="utf-8")
        sortie = io.StringIO()
        with mock.patch.object(cus, "ALLOWLIST_PATH", liste), contextlib.redirect_stdout(sortie):
            return cus.main([]), sortie.getvalue()

    def test_unique_non_scope_fait_sortir_un(self):
        rc, sortie = self._main(BARE_UNIQUE)
        self.assertEqual(rc, 1, sortie)
        self.assertIn("[UNIQUE_NOT_COMPANY_SCOPED]", sortie)
        self.assertIn("Devis.reference", sortie)

    def test_unique_scope_passe(self):
        self.assertEqual(self._main(COMPANY_SCOPED)[0], 0)

    def test_cle_autorisee_passe(self):
        cle = cus._rel(self.app_dir / "models.py") + "::Devis.reference"
        self.assertEqual(self._main(BARE_UNIQUE, allow=cle + "\n")[0], 0)

    def test_depot_reel_vert(self):
        self._restore()
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            self.assertEqual(cus.main([]), 0, sortie.getvalue()[-2000:])


if __name__ == "__main__":
    unittest.main()
