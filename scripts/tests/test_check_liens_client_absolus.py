"""AFAC94 - scripts/check_liens_client_absolus.py (arborescence temporaire)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _cliquet  # noqa: E402
import check_liens_client_absolus as guard  # noqa: E402

RELATIF = '''
def create_session(token):
    return {"pay_url": f"/api/django/public/pay/{token}/"}
'''
PUBLIC_URL = '''
def create_session(token):
    return {"pay_url": _public_url(f"/api/django/public/pay/{token}/")}
'''
BUILD_ABSOLUTE = '''
def vue(request, token):
    return request.build_absolute_uri(f"/api/django/public/pay/{token}/")
'''
DOCSTRING = '''
def vue():
    """Sert /api/django/public/pay/<token>/ (route publique)."""
    return 1
'''


def _repo(source):
    tmp = Path(tempfile.mkdtemp())
    f = tmp / guard.BACKEND / "apps" / "ventes" / "payments" / "providers.py"
    f.parent.mkdir(parents=True)
    f.write_text(source, encoding="utf-8")
    return tmp


class LiensClientAbsolusTests(unittest.TestCase):
    def test_pay_url_relatif_signale(self):
        trouves = guard.analyser(_repo(RELATIF))
        self.assertEqual(list(trouves), [
            "backend/django_core/apps/ventes/payments/providers.py::create_session"])
        erreurs = guard.verifier(trouves, set())
        self.assertIn("RELATIF", erreurs[0])
        self.assertIn("_public_url", erreurs[0])

    def test_public_url_accepte(self):
        self.assertEqual(guard.analyser(_repo(PUBLIC_URL)), {})

    def test_build_absolute_uri_accepte(self):
        self.assertEqual(guard.analyser(_repo(BUILD_ABSOLUTE)), {})

    def test_docstring_ignoree(self):
        self.assertEqual(guard.analyser(_repo(DOCSTRING)), {})

    def test_cle_morte_echoue(self):
        erreurs = guard.verifier({}, {"a.py::f"})
        self.assertEqual(len(erreurs), 1)
        self.assertIn("MORTE", erreurs[0])

    def test_depot_reel_vert(self):
        self.assertEqual(guard.verifier(guard.analyser(), _cliquet.charger(guard.BASELINE)), [])


if __name__ == "__main__":
    unittest.main()
