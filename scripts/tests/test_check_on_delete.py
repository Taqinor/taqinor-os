"""Tests AUD827 -- scripts/check_on_delete.py (cle d'identite de contenu +
garde de fraicheur de l'allowlist).

Pur stdlib (unittest), sans Django ni base -- comme la garde elle-meme. Lancer :
    python -m unittest scripts.tests.test_check_on_delete -v

Ce que ces tests verrouillent, dans l'ordre du Done= de AUD827 :
  * la cle d'allow_key est <chemin>::<Modele>.<champ>, PAS <chemin>:<ligne> --
    inserer des lignes en amont du site ne change pas la cle ;
  * ROUGE d'abord : une cle d'allowlist qui NE RESOUT PLUS vers un site
    FK/OneToOneField existant est aujourd'hui (AVANT le fix, avec l'ancien
    format path:lineno) silencieusement traitee comme une couverture valide
    -- APRES le fix, une telle cle fait echouer main() (STALE_ALLOWLIST_KEY) ;
  * une cle VIVANTE (qui resout bien vers le site courant) passe ;
  * --regenerate reecrit l'allowlist depuis l'arbre courant : les cles
    mortes disparaissent, les cles vivantes de dette CASCADE/SET_NULL
    apparaissent, et le fichier regenere fait ensuite passer main().
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_on_delete as cod  # noqa: E402


SRC_ONE_CASCADE = """\
from django.db import models


class Devis(models.Model):
    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)
"""


class TestContentIdentityKey(unittest.TestCase):
    """AUD827 -- allow_key must be <chemin>::<Modele>.<champ>, never a line
    number: inserting lines above the FK site must NOT change the key."""

    def test_key_shape(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests") as tmp:
            path = Path(tmp) / "models.py"
            path.write_text(SRC_ONE_CASCADE, encoding="utf-8")
            _rows, _findings, debt_keys = cod.check_file(path)
            self.assertEqual(len(debt_keys), 1)
            self.assertTrue(debt_keys[0].endswith("::Devis.company"))
            self.assertNotIn(":4", debt_keys[0])  # not a line-number suffix

    def test_key_survives_line_shift_above(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests") as tmp:
            path = Path(tmp) / "models.py"
            path.write_text(SRC_ONE_CASCADE, encoding="utf-8")
            _rows, _findings, before = cod.check_file(path)

            shifted = ("# padding line\n" * 25) + SRC_ONE_CASCADE
            path.write_text(shifted, encoding="utf-8")
            _rows2, _findings2, after = cod.check_file(path)

            self.assertEqual(before, after)


class _MainHarness(unittest.TestCase):
    """Runs check_on_delete.main() over a single synthetic model file by
    monkeypatching _iter_model_files/ALLOWLIST_PATH/FINANCIAL_AUDIT_DOC --
    keeps the real DJANGO_CORE scan (thousands of real FKs) out of these
    tests entirely."""

    def _run(self, model_src, allowlist_lines, argv=()):
        """allowlist_lines may contain the placeholder '{REL}', substituted
        with the model file's OWN _rel() path (only known once the file is
        written inside this call's fresh tempdir)."""
        tmpdir = tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests")
        self.addCleanup(tmpdir.cleanup)
        tmp_path = Path(tmpdir.name)
        model_file = tmp_path / "models.py"
        model_file.write_text(model_src, encoding="utf-8")
        rel = cod._rel(model_file)
        allowlist_lines = [line.replace("{REL}", rel) for line in allowlist_lines]
        allowlist_file = tmp_path / "on_delete_allowlist.txt"
        allowlist_file.write_text(
            "\n".join(allowlist_lines) + ("\n" if allowlist_lines else ""),
            encoding="utf-8")
        fin_doc = tmp_path / "on-delete-financial-audit.md"

        orig_iter = cod._iter_model_files
        orig_allow = cod.ALLOWLIST_PATH
        orig_fin = cod.FINANCIAL_AUDIT_DOC
        cod._iter_model_files = lambda: iter([model_file])
        cod.ALLOWLIST_PATH = allowlist_file
        cod.FINANCIAL_AUDIT_DOC = fin_doc

        def _restore():
            cod._iter_model_files = orig_iter
            cod.ALLOWLIST_PATH = orig_allow
            cod.FINANCIAL_AUDIT_DOC = orig_fin
        self.addCleanup(_restore)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cod.main(list(argv))
        return rc, buf.getvalue(), model_file, allowlist_file


class TestFreshnessGate(_MainHarness):
    def test_dead_key_fails_main(self):
        """ROUGE d'abord: une cle qui ne resout plus vers AUCUN site FK
        actuel doit faire echouer main() -- avant AUD827 ce meme scenario
        (rejoue avec l'ancien format path:lineno) etait accepte en silence
        comme couverture valide (c'est exactement le defaut mesure : 1598
        des 2770 cles ne resolvaient plus vers rien)."""
        rc, output, model_file, _allow = self._run(
            SRC_ONE_CASCADE, ["some/other/file.py::NoSuchModel.no_such_field"])
        self.assertEqual(rc, 1)
        self.assertIn("STALE_ALLOWLIST_KEY", output)
        self.assertIn("no_such_field", output)
        # AND the real CASCADE at Devis.company must ALSO be reported (it is
        # NOT covered by the dead key — a dead key must never cross-cover
        # an unrelated site):
        self.assertIn("UNJUSTIFIED_CASCADE", output)

    def test_live_key_passes(self):
        rc, output, _mf, _allow = self._run(
            SRC_ONE_CASCADE, ["{REL}::Devis.company"])
        self.assertEqual(rc, 0)
        self.assertNotIn("[STALE_ALLOWLIST_KEY]", output)
        self.assertNotIn("UNJUSTIFIED_CASCADE", output)

    def test_blank_and_comment_lines_ignored_not_stale(self):
        rc, output, _mf, _allow = self._run(
            SRC_ONE_CASCADE, ["# a comment", "", "   "])
        # the comment/blank lines are not real keys -> no STALE finding for
        # them, but the real CASCADE is still unjustified:
        self.assertNotIn("[STALE_ALLOWLIST_KEY]", output)
        self.assertEqual(rc, 1)
        self.assertIn("UNJUSTIFIED_CASCADE", output)


class TestRegenerate(_MainHarness):
    def test_regenerate_drops_dead_keeps_live(self):
        rc, _output, model_file, allow_file = self._run(
            SRC_ONE_CASCADE,
            ["dead/path.py::Ghost.field"],
            argv=["--regenerate"])
        self.assertEqual(rc, 0)
        content = allow_file.read_text(encoding="utf-8")
        self.assertNotIn("dead/path.py::Ghost.field", content)
        rel = cod._rel(model_file)
        self.assertIn(f"{rel}::Devis.company", content)

    def test_regenerated_file_then_passes_plain_run(self):
        # First: regenerate from a stale allowlist.
        _rc, _out, model_file, allow_file = self._run(
            SRC_ONE_CASCADE,
            ["dead/path.py::Ghost.field"],
            argv=["--regenerate"])
        regenerated = allow_file.read_text(encoding="utf-8")

        # Second run: fresh harness, seeded with the regenerated content —
        # must now pass cleanly (freshness gate green, CASCADE covered).
        tmpdir = tempfile.TemporaryDirectory(dir=ROOT / "scripts" / "tests")
        self.addCleanup(tmpdir.cleanup)
        tmp_path = Path(tmpdir.name)
        model_file2 = tmp_path / "models.py"
        model_file2.write_text(SRC_ONE_CASCADE, encoding="utf-8")
        allow_file2 = tmp_path / "on_delete_allowlist.txt"
        # Rewrite the regenerated content's path prefix to match model_file2.
        old_rel = cod._rel(model_file)
        new_rel = cod._rel(model_file2)
        allow_file2.write_text(
            regenerated.replace(old_rel, new_rel), encoding="utf-8")
        fin_doc2 = tmp_path / "on-delete-financial-audit.md"

        orig_iter = cod._iter_model_files
        orig_allow = cod.ALLOWLIST_PATH
        orig_fin = cod.FINANCIAL_AUDIT_DOC
        cod._iter_model_files = lambda: iter([model_file2])
        cod.ALLOWLIST_PATH = allow_file2
        cod.FINANCIAL_AUDIT_DOC = fin_doc2
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cod.main([])
        finally:
            cod._iter_model_files = orig_iter
            cod.ALLOWLIST_PATH = orig_allow
            cod.FINANCIAL_AUDIT_DOC = orig_fin

        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
