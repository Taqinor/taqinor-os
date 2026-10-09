"""ADEP25 - tests de scripts/check_money_fields.py (cles d'exception = identites de contenu)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_money_fields as cmf  # noqa: E402

MODELE = ("from django.db import models\n\n\nclass Produit(models.Model):\n"
          "    prix_ht = models.DecimalField(max_digits=12, decimal_places=3)\n")


def _lancer(allow):
    with tempfile.TemporaryDirectory() as tmp:
        r = Path(tmp)
        d = r / "backend" / "django_core" / "apps" / "stock"
        d.mkdir(parents=True)
        (d / "models.py").write_text(MODELE, encoding="utf-8")
        (r / "docs").mkdir()
        with mock.patch.object(cmf, "ROOT", r), \
                mock.patch.object(cmf, "DJANGO_CORE", r / "backend" / "django_core"), \
                mock.patch.object(cmf, "MONEY_AUDIT_DOC", r / "docs" / "audit.md"), \
                mock.patch.object(cmf, "DECIMAL_PLACES_ALLOWLIST", allow), \
                mock.patch.object(cmf, "_CLES_DERIVE", set()):
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cmf.main(["--decimal-places"])
            return code, buf.getvalue()


class CleContenuTests(unittest.TestCase):
    def test_cle_orpheline_rouge(self):
        code, sortie = _lancer({"backend/django_core/apps/stock/models.py::Produit.prix_ht",
                                "backend/django_core/apps/mort/models.py::X.y"})
        self.assertEqual(code, 1, sortie)
        self.assertIn("ORPHAN_ALLOWLIST_KEY", sortie)
        self.assertIn("mort/models.py::X.y", sortie)

    def test_cle_vivante_vert(self):
        code, sortie = _lancer({"backend/django_core/apps/stock/models.py::Produit.prix_ht"})
        self.assertEqual(code, 0, sortie)

    def test_derive_non_listee_rouge(self):
        code, sortie = _lancer(set())
        self.assertEqual(code, 1, sortie)
        self.assertIn("MONEY_DECIMAL_PLACES", sortie)

    def test_depot_reel_cles_pointent_un_champ(self):
        for cle in cmf.DECIMAL_PLACES_ALLOWLIST:
            rel, _, champ = cle.partition("::")
            self.assertTrue((ROOT / rel).exists(), rel)
            self.assertIn(champ.split(".")[1], (ROOT / rel).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
