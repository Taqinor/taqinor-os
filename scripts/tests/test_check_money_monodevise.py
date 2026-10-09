"""Tests YDATA22 — scripts/check_money_monodevise.py.

Pure stdlib (unittest + ast), no Django/DB needed. Run with:
    python -m unittest scripts.tests.test_check_money_monodevise -v
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_money_monodevise as cmf  # noqa: E402


def _first_class(src: str) -> ast.ClassDef:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            return node
    raise AssertionError("no class found in fixture source")


class ScanClassTests(unittest.TestCase):
    def test_money_field_without_devise_is_flagged(self):
        src = """
class Paiement(models.Model):
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=50)
"""
        info = cmf._scan_class("ventes", "apps/ventes/models.py", _first_class(src))
        self.assertIsNotNone(info)
        self.assertEqual(info.model, "Paiement")
        self.assertIn("montant", info.money_fields)
        self.assertFalse(info.has_devise)
        self.assertFalse(info.has_rate)

    def test_model_with_devise_field_is_not_flagged(self):
        src = """
class Devis(models.Model):
    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2)
    devise = models.CharField(max_length=3, default='MAD')
    taux_change = models.DecimalField(max_digits=10, decimal_places=6, default=1)
"""
        info = cmf._scan_class("ventes", "apps/ventes/models.py", _first_class(src))
        self.assertIsNotNone(info)
        self.assertTrue(info.has_devise)
        self.assertTrue(info.has_rate)

    def test_model_without_money_field_returns_none(self):
        src = """
class Client(models.Model):
    nom = models.CharField(max_length=100)
    actif = models.BooleanField(default=True)
"""
        info = cmf._scan_class("crm", "apps/crm/models.py", _first_class(src))
        self.assertIsNone(info)

    def test_bare_field_import_without_models_prefix_is_detected(self):
        # after `from django.db.models import DecimalField` — no `models.` prefix
        src = """
class LigneFacture(models.Model):
    prix_unitaire = DecimalField(max_digits=12, decimal_places=2)
"""
        info = cmf._scan_class("ventes", "apps/ventes/models.py", _first_class(src))
        self.assertIsNotNone(info)
        self.assertIn("prix_unitaire", info.money_fields)

    def test_non_field_assignment_is_ignored(self):
        src = """
class Produit(models.Model):
    montant_max = 100  # plain constant, not a Field() call
"""
        info = cmf._scan_class("stock", "apps/stock/models.py", _first_class(src))
        self.assertIsNone(info)


class RenderAuditMarkdownTests(unittest.TestCase):
    def test_splits_models_by_devise_presence(self):
        models_ = [
            cmf.ModelMoneyInfo(
                app="ventes", relpath="apps/ventes/models.py", model="Paiement",
                lineno=10, money_fields=["montant"], has_devise=False, has_rate=False,
            ),
            cmf.ModelMoneyInfo(
                app="ventes", relpath="apps/ventes/models.py", model="Devis",
                lineno=20, money_fields=["montant_ttc"], has_devise=True, has_rate=True,
            ),
        ]
        doc = cmf.render_audit_markdown(models_)
        self.assertIn("Paiement", doc)
        self.assertIn("Devis", doc)
        self.assertIn("Money-bearing models scanned: **2**", doc)
        self.assertIn("Already carry an explicit devise/currency field: **1**", doc)
        self.assertIn("Assume mono-devise MAD implicitly (no devise field): **1**", doc)


class ScanRepoSmokeTests(unittest.TestCase):
    """Integration-ish smoke test over the REAL repo (no fixtures) — proves the
    scanner runs cleanly end to end and finds the known reference models."""

    def test_scan_finds_known_multi_currency_models(self):
        models_ = cmf.scan_money_models()
        self.assertGreater(len(models_), 0)
        by_name = {m.model for m in models_}
        self.assertIn("Devis", by_name)
        self.assertIn("Facture", by_name)
        devis = next(m for m in models_ if m.model == "Devis" and m.app == "ventes")
        self.assertTrue(devis.has_devise)
        self.assertTrue(devis.has_rate)

    def test_main_exits_zero_when_no_finding(self):
        # ENF13 — blocking: main() is 0 only because the repo has 0 finding.
        self.assertEqual(cmf.find_violations(cmf.scan_money_models()), [])
        self.assertEqual(cmf.main(), 0)


class ViolationsTests(unittest.TestCase):
    """ENF13 — DEVISE_MONTANT / DEVISE_DEFAUT are blocking findings."""

    def _violations(self, src):
        info = cmf._scan_class("achats", "apps/achats/models.py", _first_class(src))
        return cmf.find_violations([info])

    def test_montant_en_devise_sans_devise_est_un_constat(self):
        src = """
class Ligne(models.Model):
    prix_achat = models.DecimalField(max_digits=12, decimal_places=2)
    prix_achat_devise = models.DecimalField(max_digits=12, decimal_places=2)
"""
        out = self._violations(src)
        self.assertEqual(len(out), 1)
        self.assertIn("DEVISE_MONTANT", out[0])

    def test_accesseur_devise_satisfait_la_regle(self):
        src = """
class Ligne(models.Model):
    prix_achat_devise = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def devise(self):
        return self.parent.devise
"""
        self.assertEqual(self._violations(src), [])

    def test_champ_devise_satisfait_la_regle(self):
        src = """
class Doc(models.Model):
    montant_ttc_devise = models.DecimalField(max_digits=12, decimal_places=2)
    devise = models.CharField(max_length=3, default='MAD')
"""
        self.assertEqual(self._violations(src), [])

    def test_defaut_non_mad_est_un_constat(self):
        src = """
class Doc(models.Model):
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    devise = models.CharField(max_length=3, default='EUR')
"""
        out = self._violations(src)
        self.assertEqual(len(out), 1)
        self.assertIn("DEVISE_DEFAUT", out[0])

    def test_defaut_mad_ou_vide_ou_enum_accepte(self):
        for dflt in ("'MAD'", "''", "DeviseAchat.MAD"):
            src = f"""
class Doc(models.Model):
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    devise = models.CharField(max_length=3, default={dflt})
"""
            self.assertEqual(self._violations(src), [], dflt)


if __name__ == "__main__":
    unittest.main()
