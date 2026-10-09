"""APRF28 — scripts/check_exports_bornes.py (fixtures temporaires, exécution
réelle du script en sous-processus).

    python -m unittest scripts.tests.test_check_exports_bornes -v
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "scripts" / "check_exports_bornes.py"
sys.path.insert(0, str(ROOT / "scripts"))

import check_exports_bornes as guard  # noqa: E402


class _Arbre(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.apps = self.racine / "backend" / "django_core" / "apps" / "x"
        self.apps.mkdir(parents=True)

    def ecrire(self, nom, src):
        (self.apps / nom).write_text(textwrap.dedent(src), encoding="utf-8")

    def lancer(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--racine", str(self.racine)],
            capture_output=True, stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        sortie = (r.stdout + r.stderr).decode("utf-8", errors="replace")
        return r.returncode, sortie


VUE_NON_BORNEE = """\
    def export_view(request):
        return build_xlsx_response(Modele.objects.all())
"""


class DetectionTests(_Arbre):
    def test_vue_non_bornee_echoue_et_nomme_la_vue(self):
        self.ecrire("views.py", VUE_NON_BORNEE)
        code, out = self.lancer()
        self.assertEqual(code, 1, out)
        self.assertIn("views.py::export_view", out)

    def test_service_appele_par_vue_non_bornee_nomme_le_service(self):
        self.ecrire("views.py", """\
            def export_view(request):
                return export_x(Modele.objects.all())
        """)
        self.ecrire("services.py", """\
            def export_x(qs):
                return build_xlsx_response(qs)
        """)
        code, out = self.lancer()
        self.assertEqual(code, 1, out)
        self.assertIn("services.py::export_x", out)
        self.assertNotIn("views.py::export_view", out)

    def test_vue_qui_appelle_should_async_export_passe(self):
        self.ecrire("views.py", """\
            def export_view(request):
                qs = Modele.objects.all()
                if should_async_export(qs.count()):
                    return Response(status=202)
                return build_xlsx_response(qs)
        """)
        code, out = self.lancer()
        self.assertEqual(code, 0, out)

    def test_service_borne_par_sa_vue_passe(self):
        self.ecrire("views.py", """\
            def export_view(request):
                qs = Modele.objects.all()
                if should_async_export(qs.count()):
                    return Response(status=202)
                return export_x(qs)
        """)
        self.ecrire("services.py", """\
            def export_x(qs):
                return build_xlsx_response(qs)
        """)
        code, out = self.lancer()
        self.assertEqual(code, 0, out)

    def test_refus_d_ids_vides_passe(self):
        self.ecrire("views.py", """\
            def export_view(request):
                ids = request.data.get('ids')
                if not ids:
                    return Response(status=400)
                return workbook_bytes(ids)
        """)
        code, out = self.lancer()
        self.assertEqual(code, 0, out)

    def test_openpyxl_workbook_direct_est_vu(self):
        self.ecrire("views.py", """\
            import openpyxl
            def export_view(request):
                wb = openpyxl.Workbook()
                return wb
        """)
        code, _ = self.lancer()
        self.assertEqual(code, 1)

    def test_les_tests_sont_hors_perimetre(self):
        tests = self.apps / "tests"
        tests.mkdir()
        (tests / "test_export.py").write_text(
            textwrap.dedent(VUE_NON_BORNEE), encoding="utf-8")
        code, out = self.lancer()
        self.assertEqual(code, 0, out)


class ExceptionsTests(_Arbre):
    CLE = "backend/django_core/apps/x/views.py::export_view"

    def test_exception_datee_et_motivee_passe(self):
        self.ecrire("views.py", VUE_NON_BORNEE)
        erreurs, _ = guard.evaluer(self.racine,
                                   {self.CLE: ("2026-10-09", "raison")})
        self.assertEqual(erreurs, [])

    def test_exception_sans_date_echoue(self):
        """Test-du-test : sans la vérification de date, ce cas passerait."""
        self.ecrire("views.py", VUE_NON_BORNEE)
        erreurs, _ = guard.evaluer(self.racine, {self.CLE: ("", "raison")})
        self.assertTrue(any("sans date" in e for e in erreurs), erreurs)
        erreurs, _ = guard.evaluer(self.racine, {self.CLE: ("hier", "raison")})
        self.assertTrue(any("sans date" in e for e in erreurs), erreurs)

    def test_exception_sans_raison_ou_morte_echoue(self):
        self.ecrire("views.py", VUE_NON_BORNEE)
        erreurs, _ = guard.evaluer(self.racine, {self.CLE: ("2026-10-09", " ")})
        self.assertTrue(any("sans raison" in e for e in erreurs))
        self.ecrire("views.py", "def ok():\n    return 1\n")
        erreurs, _ = guard.evaluer(self.racine,
                                   {self.CLE: ("2026-10-09", "raison")})
        self.assertTrue(any("morte" in e for e in erreurs))


class DepotTests(unittest.TestCase):
    def test_depot_vert(self):
        self.assertEqual(guard.main([]), 0)

    def test_exceptions_toutes_datees_et_motivees(self):
        for cle, (date, raison) in guard.EXCEPTIONS.items():
            self.assertTrue(guard._date_valide(date), cle)
            self.assertTrue(raison.strip(), cle)


if __name__ == "__main__":
    unittest.main()
