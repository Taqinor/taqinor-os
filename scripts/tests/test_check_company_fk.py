"""ATST41 (C-ATST-006) — scripts/check_company_fk.py joue son cas d'échec.

Pure stdlib (unittest), no Django. Run:
    python -m unittest scripts.tests.test_check_company_fk -v
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_company_fk as ccf  # noqa: E402 — après sys.path (D-ENF22)

ENTETE = "from django.db import models\nfrom core.models import TenantModel\n\n\n"
SANS_SOCIETE = "class Facture(models.Model):\n    total_ttc = models.DecimalField(max_digits=12, decimal_places=2)\n"
AVEC_SOCIETE = ("class Facture(models.Model):\n"
                "    company = models.ForeignKey('authentication.Company', on_delete=models.CASCADE)\n")
LIGNE = ("\n\nclass LigneFacture(models.Model):\n"
         "    facture = models.ForeignKey(Facture, on_delete=models.CASCADE)\n")
TENANT = "class Reglage(TenantModel):\n    cle = models.CharField(max_length=20)\n"


class CheckCompanyFkTests(unittest.TestCase):
    def _jouer(self, source, exempt=()):
        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            app = racine / "backend" / "django_core" / "apps" / "zzfake"
            app.mkdir(parents=True)
            (app / "models.py").write_text(ENTETE + source, encoding="utf-8")
            sortie = io.StringIO()
            with mock.patch.object(ccf, "ROOT", racine), \
                    mock.patch.object(ccf, "APPS_DIR", app.parent), \
                    mock.patch.object(ccf, "_load_exempt", return_value=set(exempt)), \
                    contextlib.redirect_stdout(sortie):
                rc = ccf.main([])
        return rc, sortie.getvalue()

    def test_modele_metier_sans_societe_rougit(self):
        """Mutant `if not ok and key not in exempt:` → `if False:` ⇒ rc 0, échec."""
        rc, sortie = self._jouer(SANS_SOCIETE)
        self.assertEqual(rc, 1, sortie)
        self.assertIn("zzfake.Facture  [MISSING]", sortie)
        self.assertIn("violation(s) found", sortie)

    def test_fk_transitive_et_exemption_passent(self):
        """Point fixe de `resolve_has_company` retiré ⇒ LigneFacture MISSING, échec."""
        for source in (AVEC_SOCIETE, AVEC_SOCIETE + LIGNE, TENANT):
            with self.subTest(source=source.splitlines()[0]):
                rc, sortie = self._jouer(source)
                self.assertEqual(rc, 0, sortie)
                self.assertNotIn("[MISSING]", sortie)
                self.assertIn("[OK]", sortie)
        rc, sortie = self._jouer(SANS_SOCIETE, exempt={"zzfake.Facture"})
        self.assertEqual(rc, 0, sortie)
        self.assertIn("zzfake.Facture  [EXEMPT]", sortie)

    def test_depot_reel_vert(self):
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            rc = ccf.main([])
        self.assertEqual(rc, 0, sortie.getvalue()[-2000:])


if __name__ == "__main__":
    unittest.main()
