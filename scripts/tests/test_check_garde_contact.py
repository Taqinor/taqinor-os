"""ACRM50 - scripts/check_garde_contact.py."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_garde_contact as garde  # noqa: E402

SANS_GARDE = (
    "def poser(lead):\n"
    "    return RelanceEtape.objects.create(lead=lead)\n"
)
AVEC_GARDE = (
    "def poser(lead):\n"
    "    if not peut_contacter(lead):\n"
    "        return None\n"
    "    return RelanceEtape.objects.create(lead=lead)\n"
)


def _lancer():
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        code = garde.main([])
    return code, sortie.getvalue()


class GardeContactTests(unittest.TestCase):
    def test_creation_sans_garde_detectee(self):
        r = garde.analyser_source(SANS_GARDE, "apps/crm/x.py")
        self.assertEqual(len(r), 1)
        cle, ligne, fonction, genre = r[0]
        self.assertEqual((fonction, genre, ligne), ("poser", "touche", 2))
        self.assertEqual(cle, "apps/crm/x.py::poser::touche")

    def test_creation_gardee_ok(self):
        self.assertEqual(garde.analyser_source(AVEC_GARDE, "apps/crm/x.py"), [])

    def test_wame_et_mail_detectes(self):
        src = ("def a(n):\n    return f'https://wa.me/{n}'\n"
               "def b(t):\n    send_mail('s', 'b', 'f', [t])\n")
        genres = sorted(g for _, _, _, g in garde.analyser_source(src, "f.py"))
        self.assertEqual(genres, ["email", "wa.me"])

    def test_docstring_wame_ignoree(self):
        src = 'def a():\n    """lien wa.me/xxx"""\n    return 1\n'
        self.assertEqual(garde.analyser_source(src, "f.py"), [])

    def test_depot_vert(self):
        code, sortie = _lancer()
        self.assertEqual(code, 0, sortie)

    def test_test_du_test_garde_retiree_rougit(self):
        sauve = set(garde.GARDES_RECONNUES)
        try:
            garde.GARDES_RECONNUES.clear()
            garde.GARDES_RECONNUES.add("nom_inexistant")
            code, sortie = _lancer()
        finally:
            garde.GARDES_RECONNUES.clear()
            garde.GARDES_RECONNUES.update(sauve)
        self.assertEqual(code, 1)
        self.assertIn("sans garde de contact", sortie)


if __name__ == "__main__":
    unittest.main()
