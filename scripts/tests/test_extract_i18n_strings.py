"""Tests NTI18N1 — scripts/extract_i18n_strings.py.

Pure stdlib (unittest), zero Django/DB/npm dependency. Run with:
    python -m unittest scripts.tests.test_extract_i18n_strings -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import extract_i18n_strings as eis  # noqa: E402


class HasFrenchHintTests(unittest.TestCase):
    def test_accented_text_detected(self):
        self.assertTrue(eis.has_french_hint("Créer un client"))

    def test_common_word_detected_without_accent(self):
        self.assertTrue(eis.has_french_hint("Nouveau devis pour ce client"))

    def test_english_or_technical_text_not_flagged(self):
        self.assertFalse(eis.has_french_hint("OK"))
        self.assertFalse(eis.has_french_hint("PDF"))
        self.assertFalse(eis.has_french_hint("id123"))


class CountHardcodedStringsTests(unittest.TestCase):
    def test_counts_jsx_text_node(self):
        src = "<CardTitle>Bons de commande</CardTitle>"
        self.assertEqual(eis.count_hardcoded_strings(src), 1)

    def test_counts_common_attribute(self):
        src = '<Input placeholder="Rechercher un client" />'
        self.assertEqual(eis.count_hardcoded_strings(src), 1)

    def test_ignores_expression_content(self):
        # Le contenu d'une expression JS {..} (y compris un appel t()) ne doit
        # JAMAIS être compté comme chaîne en dur.
        src = "<CardTitle>{t('crm.title')}</CardTitle>"
        self.assertEqual(eis.count_hardcoded_strings(src), 0)

    def test_ignores_non_french_short_tokens(self):
        src = "<Badge>OK</Badge>"
        self.assertEqual(eis.count_hardcoded_strings(src), 0)


class IsMigratedTests(unittest.TestCase):
    def test_detects_uset_call(self):
        self.assertTrue(eis.is_migrated("const t = useT()\nreturn <div>{t('x')}</div>"))

    def test_detects_usei18n_call(self):
        self.assertTrue(eis.is_migrated("const { t } = useI18n()"))

    def test_no_hook_call_is_not_migrated(self):
        self.assertFalse(eis.is_migrated("return <div>Bonjour</div>"))

    def test_import_alone_without_call_is_not_migrated(self):
        # Un import seul (jamais invoqué) ne compte pas — évite un
        # faux-positif « migré » sur un fichier qui n'utilise en réalité rien.
        self.assertFalse(
            eis.is_migrated("import { useT } from '../../i18n'\nfunction X() { return null }")
        )


class ResolveImportTests(unittest.TestCase):
    def test_resolves_jsx_file(self):
        base = ROOT / "frontend" / "src" / "features" / "crm"
        resolved = eis.resolve_import(base, "../../pages/crm/ClientList")
        self.assertIsNotNone(resolved)
        self.assertTrue(str(resolved).replace("\\", "/").endswith(
            "frontend/src/pages/crm/ClientList.jsx"))

    def test_missing_file_returns_none(self):
        base = ROOT / "frontend" / "src" / "features" / "crm"
        self.assertIsNone(eis.resolve_import(base, "./NoSuchFileEver12345"))


class GatedModulesTests(unittest.TestCase):
    def test_gated_modules_include_known_parked_verticals(self):
        gated = eis.gated_modules()
        # SOL6 — ces verticaux sont parqués (édition solaire) ; si un jour ils
        # disparaissent du glob négatif de moduleRoutes.jsx, ce test échoue
        # bruyamment plutôt qu'un compte silencieusement faux.
        for key in ("agriculture", "education", "sante"):
            self.assertIn(key, gated)


class BuildReportTests(unittest.TestCase):
    def test_report_shape_and_no_gated_module_leaks_in(self):
        report = eis.build_report()
        self.assertIn("total_components", report)
        self.assertIn("coverage_pct", report)
        self.assertGreater(report["total_components"], 0)
        domains = set(report["domains"].keys())
        for gated_key in ("agriculture", "education", "sante"):
            self.assertNotIn(gated_key, domains)

    def test_coverage_pct_consistent_with_counts(self):
        report = eis.build_report()
        total = report["total_components"]
        migrated = report["migrated_components"]
        expected = round(100.0 * migrated / total, 1) if total else 0.0
        self.assertEqual(report["coverage_pct"], expected)


if __name__ == "__main__":
    unittest.main()
