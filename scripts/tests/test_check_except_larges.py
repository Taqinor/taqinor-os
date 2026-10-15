"""Tests ENF22 — scripts/check_except_larges.py (« except large journalisant »).

Stdlib pure (unittest), aucune base. Run :
    python -m unittest scripts.tests.test_check_except_larges -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_except_larges as guard  # noqa: E402 — après sys.path/setup() (D-ENF22)


def silencieux(src):
    return guard.silencieux_dans(src)


class ExceptLargesTests(unittest.TestCase):
    def test_silencieux_pass(self):
        src = "def f():\n    try:\n        x()\n    except Exception:  # noqa: BLE001\n        pass\n"
        self.assertEqual(silencieux(src), ["f"])

    def test_bare_except_et_baseexception(self):
        src = ("def f():\n    try:\n        x()\n    except:\n        return 1\n"
               "def g():\n    try:\n        x()\n    except BaseException:\n        return 2\n")
        self.assertEqual(silencieux(src), ["f", "g"])

    def test_logger_ok(self):
        src = ("def f():\n    try:\n        x()\n    except Exception:\n"
               "        logger.warning('x a echoue', exc_info=True)\n        return None\n")
        self.assertEqual(silencieux(src), [])

    def test_reraise_ok(self):
        src = "def f():\n    try:\n        x()\n    except Exception:\n        raise\n"
        self.assertEqual(silencieux(src), [])

    def test_sentry_et_warnings_ok(self):
        src = ("def f():\n    try:\n        x()\n    except Exception as e:\n"
               "        sentry_sdk.capture_exception(e)\n"
               "def g():\n    try:\n        x()\n    except Exception:\n"
               "        warnings.warn('x')\n")
        self.assertEqual(silencieux(src), [])

    def test_exception_precise_ignoree(self):
        src = "def f():\n    try:\n        x()\n    except KeyError:\n        pass\n"
        self.assertEqual(silencieux(src), [])

    def test_methode_de_classe_qualifiee(self):
        src = ("class A:\n    def m(self):\n        try:\n            x()\n"
               "        except (ValueError, Exception):\n            pass\n")
        self.assertEqual(silencieux(src), ["A.m"])

    def test_print_nest_pas_un_log(self):
        src = "def f():\n    try:\n        x()\n    except Exception:\n        print('x')\n"
        self.assertEqual(silencieux(src), ["f"])

    def test_depot_reel_vert(self):
        self.assertEqual(guard.main([]), 0)

    def test_chargement_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            allow = Path(tmp) / "a.txt"
            allow.write_text("# c\nbackend/django_core/apps/x/y.py::f\n", encoding="utf-8")
            self.assertEqual(guard._load_allowlist(allow),
                             {"backend/django_core/apps/x/y.py::f"})


if __name__ == "__main__":
    unittest.main()
