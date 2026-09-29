"""Tests de scripts/check_test_package_shadow.py (ERR-QAH-CRM-TESTS-MASQUES).

Stdlib pur (unittest), aucune base de donnees, aucun Django.
Lancer :
    python -m unittest scripts.tests.test_check_test_package_shadow -v
"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import check_test_package_shadow as guard  # noqa: E402


def _make_app(apps_dir, name, has_tests_module=False, has_tests_package=False):
    app_dir = os.path.join(apps_dir, name)
    os.makedirs(app_dir, exist_ok=True)
    open(os.path.join(app_dir, "__init__.py"), "w").close()
    if has_tests_module:
        with open(os.path.join(app_dir, "tests.py"), "w") as fh:
            fh.write("# module\n")
    if has_tests_package:
        pkg = os.path.join(app_dir, "tests")
        os.makedirs(pkg, exist_ok=True)
        open(os.path.join(pkg, "__init__.py"), "w").close()
        with open(os.path.join(pkg, "test_x.py"), "w") as fh:
            fh.write("# in package\n")


class FindShadowedAppsTests(unittest.TestCase):
    def test_real_repo_is_currently_clean(self):
        """La reparation ERR-QAH-CRM-TESTS-MASQUES a aplati apps/crm/tests/ :
        le depot reel ne doit plus rien remonter."""
        self.assertEqual(guard.find_shadowed_apps(), [])

    def test_flags_an_app_with_both_tests_py_and_tests_package(self):
        """LE CAS REEL : une app qui a les deux doit rougir (c'est exactement
        ce que apps/crm avait jusqu'a CALX106)."""
        with tempfile.TemporaryDirectory() as tmp:
            django_root = os.path.join(tmp, "backend", "django_core")
            apps_dir = os.path.join(django_root, "apps")
            os.makedirs(apps_dir, exist_ok=True)
            _make_app(apps_dir, "crm", has_tests_module=True,
                      has_tests_package=True)
            _make_app(apps_dir, "ventes", has_tests_module=True,
                      has_tests_package=False)
            self.assertEqual(
                guard.find_shadowed_apps(django_root), ["apps.crm"])

    def test_module_only_or_package_only_is_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            django_root = os.path.join(tmp, "backend", "django_core")
            apps_dir = os.path.join(django_root, "apps")
            os.makedirs(apps_dir, exist_ok=True)
            _make_app(apps_dir, "onlymodule", has_tests_module=True,
                      has_tests_package=False)
            _make_app(apps_dir, "onlypackage", has_tests_module=False,
                      has_tests_package=True)
            self.assertEqual(guard.find_shadowed_apps(django_root), [])

    def test_main_exits_nonzero_when_shadowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            django_root = os.path.join(tmp, "backend", "django_core")
            apps_dir = os.path.join(django_root, "apps")
            os.makedirs(apps_dir, exist_ok=True)
            _make_app(apps_dir, "crm", has_tests_module=True,
                      has_tests_package=True)
            self.assertEqual(
                guard.find_shadowed_apps(django_root), ["apps.crm"])


if __name__ == "__main__":
    unittest.main()
