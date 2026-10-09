"""ACAL348 — scripts/check_calepinage_routes_sous_contrat.py (fixtures factices)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _cliquet  # noqa: E402
import check_calepinage_routes_sous_contrat as guard  # noqa: E402

VUES = '''
from rest_framework.decorators import action
from rest_framework import viewsets


class CalepinageViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=["get"], url_path="avec-contrat")
    def avec_contrat(self, request, pk=None):
        pass

    @action(detail=True, methods=["get"], url_path="sans-contrat")
    def sans_contrat(self, request, pk=None):
        pass

    @action(detail=True, methods=["post"], url_path="ecrit")
    def ecrit(self, request, pk=None):
        pass

    @action(detail=True, methods=["get"], url_path=r"rapport\\.pdf")
    def rapport(self, request, pk=None):
        pass


@action(detail=True, url_path="greffee")
def greffee(self, request, pk=None):
    pass
'''


def _repo(samples):
    tmp = Path(tempfile.mkdtemp())
    vues = tmp / guard.APP / "views" / "x.py"
    vues.parent.mkdir(parents=True)
    vues.write_text(VUES, encoding="utf-8")
    cs = tmp / guard.APP / "contract_samples"
    cs.mkdir(parents=True)
    for nom, contenu in samples.items():
        (cs / nom).write_text(json.dumps(contenu), encoding="utf-8")
    return tmp


class RoutesSousContratTests(unittest.TestCase):
    def test_route_get_sans_contrat_rougit(self):
        root = _repo({"a.json": {"endpoint": "GET /api/django/calepinage/calepinages/<int:pk>/avec-contrat/"}})
        d = guard.dettes(root)
        self.assertIn("GET calepinages/<>/sans-contrat", d)
        self.assertIn("GET calepinages/<>/greffee", d)
        self.assertNotIn("GET calepinages/<>/avec-contrat", d)
        self.assertNotIn("GET calepinages/<>/ecrit", d)  # POST : hors périmètre
        self.assertTrue(guard.verifier(d, set()))

    def test_route_fichier_exemptee(self):
        root = _repo({})
        self.assertIn("calepinages/<>/rapport.pdf", guard.routes_get(root))
        self.assertNotIn("GET calepinages/<>/rapport.pdf", guard.dettes(root))

    def test_endpoint_imbrique_et_sans_verbe_compte(self):
        root = _repo({"a.json": {"exemple": {"documents": [
            {"endpoint": "/api/django/calepinage/calepinages/1/sans-contrat/"}]}}})
        self.assertNotIn("GET calepinages/<>/sans-contrat", guard.dettes(root))

    def test_base_ne_croit_pas(self):
        chemin = Path(tempfile.mkdtemp()) / "b.txt"
        _cliquet.ecrire(chemin, {"a"}, "", "r")
        with self.assertRaises(ValueError):
            _cliquet.ecrire(chemin, {"a", "b"}, "", "r")
        self.assertTrue(guard.verifier(set(), {"GET x"}))  # clé morte

    def test_depot_reel_vert(self):
        base = {c.replace("~", " ") for c in _cliquet.charger(guard.BASELINE)}
        self.assertEqual(guard.verifier(guard.dettes(), base), [])


if __name__ == "__main__":
    unittest.main()
