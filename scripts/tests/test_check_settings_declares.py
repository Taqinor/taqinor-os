"""ADEP20 - scripts/check_settings_declares.py (dépôt factice en tmp)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _cliquet  # noqa: E402
import check_settings_declares as guard  # noqa: E402

SETTINGS = "DEBUG = True\nCLE_DECLAREE = 1\n"


def _repo(code, settings=SETTINGS):
    tmp = Path(tempfile.mkdtemp())
    s = tmp / guard.SETTINGS_DIR / "base.py"
    s.parent.mkdir(parents=True)
    s.write_text(settings, encoding="utf-8")
    m = tmp / guard.BACKEND / "apps" / "x" / "services.py"
    m.parent.mkdir(parents=True)
    m.write_text(code, encoding="utf-8")
    return tmp


class SettingsDeclaresTests(unittest.TestCase):
    def test_cle_non_declaree_rouge(self):
        root = _repo("from django.conf import settings\n\n\n"
                     "def f():\n    return getattr(settings, 'NOUVELLE_CLE', None)\n"
                     "\n\ndef g():\n    return settings.AUTRE_CLE\n")
        trouvees = guard.lectures_non_declarees(root)
        self.assertEqual({c.split("::")[1] for c in trouvees}, {"NOUVELLE_CLE", "AUTRE_CLE"})
        erreurs = guard.verifier(trouvees, set())
        self.assertIn("n'est déclarée dans aucun settings", erreurs[0])

    def test_repli_environ_vert(self):
        root = _repo("import os\nfrom django.conf import settings\n\n\n"
                     "def f():\n    v = getattr(settings, 'JETON', None)\n"
                     "    return v or os.environ.get('JETON', '')\n")
        self.assertEqual(guard.lectures_non_declarees(root), set())

    def test_cle_declaree_vert(self):
        root = _repo("from django.conf import settings\n\n\n"
                     "def f():\n    return settings.CLE_DECLAREE, settings.DEBUG, "
                     "getattr(settings, 'MEDIA_ROOT', '')\n")
        self.assertEqual(guard.lectures_non_declarees(root), set())

    def test_ligne_morte_rouge(self):
        erreurs = guard.verifier(set(), {"backend/x.py::VIEILLE_CLE"})
        self.assertEqual(len(erreurs), 1)
        self.assertIn("MORTE", erreurs[0])

    def test_tests_exclus(self):
        root = _repo("x = 1\n")
        t = root / guard.BACKEND / "apps" / "x" / "tests" / "test_a.py"
        t.parent.mkdir(parents=True)
        t.write_text("from django.conf import settings\nsettings.TESTONLY\n", encoding="utf-8")
        self.assertEqual(guard.lectures_non_declarees(root), set())

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(guard.lectures_non_declarees(),
                                        _cliquet.charger(guard.BASELINE)), [])


if __name__ == "__main__":
    unittest.main()
