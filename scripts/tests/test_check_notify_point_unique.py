"""Tests APAR63 — scripts/check_notify_point_unique.py.

Stdlib pure (unittest). Run :
    python -m unittest scripts.tests.test_check_notify_point_unique -v
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_notify_point_unique as guard  # noqa: E402

CREATE = """
from apps.notifications.models import Notification

def alerter(user):
    Notification.objects.create(user=user, title='x')
"""
BULK = """
def alerter(rows):
    Notification.objects.bulk_create(rows)
"""
CONSTRUCTEUR = """
def alerter():
    return Notification(title='x')
"""
PROPRE = """
from apps.notifications.services import notify_many

def alerter(users):
    notify_many(users, 'x')
"""


class CheckNotifyPointUniqueTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.backend = base / "backend" / "django_core"
        (self.backend / "apps" / "adsengine").mkdir(parents=True)
        (self.backend / "apps" / "notifications").mkdir(parents=True)
        self.allow = base / "allow.txt"
        self._orig = (guard.ROOT, guard.BACKEND, guard.ALLOWLIST_PATH)
        guard.ROOT = base
        guard.BACKEND = self.backend
        guard.ALLOWLIST_PATH = self.allow

    def tearDown(self):
        guard.ROOT, guard.BACKEND, guard.ALLOWLIST_PATH = self._orig
        self._tmp.cleanup()

    def _ecrire(self, rel, source):
        chemin = self.backend / rel
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(source, encoding="utf-8")

    def _run(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = guard.main([])
        return code, out.getvalue()

    def test_create_hors_services_rouge(self):
        self._ecrire("apps/adsengine/alerts.py", CREATE)
        code, sortie = self._run()
        self.assertEqual(code, 1)
        self.assertIn("apps/adsengine/alerts.py:5", sortie)
        self.assertIn("notify()/notify_many()", sortie)

    def test_bulk_create_rouge(self):
        self._ecrire("apps/adsengine/alerts.py", BULK)
        self.assertEqual(self._run()[0], 1)

    def test_constructeur_rouge(self):
        self._ecrire("apps/adsengine/alerts.py", CONSTRUCTEUR)
        self.assertEqual(self._run()[0], 1)

    def test_services_tests_migrations_exclus(self):
        self._ecrire("apps/notifications/services.py", CREATE)
        self._ecrire("apps/adsengine/tests/test_x.py", CREATE)
        self._ecrire("apps/adsengine/tests_y.py", CREATE)
        self._ecrire("apps/adsengine/migrations/0001_x.py", CREATE)
        self.assertEqual(self._run()[0], 0)

    def test_appel_notify_many_vert(self):
        self._ecrire("apps/adsengine/alerts.py", PROPRE)
        self.assertEqual(self._run()[0], 0)

    def test_entree_sans_justification_refusee(self):
        self._ecrire("apps/adsengine/alerts.py", CREATE)
        self.allow.write_text("backend/django_core/apps/adsengine/alerts.py::"
                              "alerter\n", encoding="utf-8")
        code, sortie = self._run()
        self.assertEqual(code, 1)
        self.assertIn("SANS justification", sortie)

    def test_entree_justifiee_vert_puis_morte_rouge(self):
        self._ecrire("apps/adsengine/alerts.py", CREATE)
        self.allow.write_text("backend/django_core/apps/adsengine/alerts.py::"
                              "alerter  # dette gelée\n", encoding="utf-8")
        self.assertEqual(self._run()[0], 0)
        self._ecrire("apps/adsengine/alerts.py", PROPRE)
        code, sortie = self._run()
        self.assertEqual(code, 1)
        self.assertIn("MORTES", sortie)


if __name__ == "__main__":
    unittest.main()
