"""Tests YAPIC6 — scripts/check_openapi_schema.py.

Pure stdlib (unittest), no Django, no schema generation. Run:
    python -m unittest scripts.tests.test_check_openapi_schema -v

Prouve le critere « introduire volontairement un serializer ambigu fait rougir
le job » SANS payer les ~3 min de generation du schema : le ratchet est teste
sur des journaux drf-spectacular synthetiques + la vraie base de reference
versionnee.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_openapi_schema as cos  # noqa: E402

GUESS = ("unable to guess serializer. This is graceful fallback handling for "
         "APIViews. Consider using GenericAPIView as view base class, if view "
         "is under your control.")


def _line(path, severity, identity, msg):
    return f"{path}: {severity} [{identity}]: {msg}"


class ParseLogTests(unittest.TestCase):
    def test_tagged_warning_and_error_are_captured(self):
        log = "\n".join([
            _line("/a/b/views.py:12", "Error", "FooView", GUESS),
            _line("/a/b/serializers.py", "Warning", "BarViewSet > BarSerializer",
                  'unable to resolve type hint for function "get_x". Consider '
                  'using a type hint.'),
        ])
        sigs = cos.parse_log(log)
        self.assertEqual(len(sigs), 2)
        self.assertTrue(any(s.startswith("Error|FooView|") for s in sigs))
        self.assertTrue(
            any(s.startswith("Warning|BarViewSet > BarSerializer|") for s in sigs))

    def test_signature_ignores_file_path_and_line_number(self):
        """Un decalage de lignes ne doit JAMAIS invalider une entree existante."""
        a = cos.parse_log(_line("backend/apps/x/views.py:12", "Error", "FooView", GUESS))
        b = cos.parse_log(_line("backend/apps/x/views.py:987", "Error", "FooView", GUESS))
        c = cos.parse_log(_line("D:/autre/chemin/views.py", "Error", "FooView", GUESS))
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_global_warning_gets_the_global_identity(self):
        log = ('Warning: operationId "crm_leads_retrieve" has collisions '
               "[('/api/crm/leads/', 'get'), ('/api/crm/leads/{id}/', 'get')]. "
               "resolving with numeral suffixes.")
        sigs = cos.parse_log(log)
        self.assertEqual(len(sigs), 1)
        self.assertTrue(next(iter(sigs)).startswith("Warning|<global>|"))

    def test_enum_hash_suffix_is_normalised(self):
        base = ("Warning: encountered multiple names for the same choice set "
                "({name}). Add an entry to ENUM_NAME_OVERRIDES to fix the naming.")
        a = cos.parse_log(base.format(name="ModePaiement8f6Enum"))
        b = cos.parse_log(base.format(name="ModePaiementbbc1Enum"))
        self.assertEqual(a, b)

    def test_signature_never_ends_on_whitespace(self):
        """La base de reference est relue avec .strip() : une signature finissant
        par un espace ne se reconnaitrait plus elle-meme."""
        sig = next(iter(cos.parse_log(_line("v.py", "Error", "FooView", GUESS))))
        self.assertEqual(sig, sig.rstrip())

    def test_non_finding_lines_are_ignored(self):
        self.assertEqual(cos.parse_log("Schema generation summary:\nWarnings: 12\n"
                                       "random noise\n"), set())


class RatchetTests(unittest.TestCase):
    """Le vrai fichier scripts/openapi_schema_allow.txt sert de reference."""

    @classmethod
    def setUpClass(cls):
        cls.baseline = cos.load_baseline()

    def test_committed_baseline_is_present_and_well_formed(self):
        self.assertGreater(len(self.baseline), 100)
        for entry in self.baseline:
            self.assertEqual(entry.count("|") >= 2, True, entry)
            self.assertIn(entry.split("|", 1)[0], ("Warning", "Error"), entry)
            self.assertEqual(entry, entry.strip(), entry)

    def test_a_new_ambiguous_serializer_is_reported(self):
        """Le critere de YAPIC6 : une NOUVELLE vue sans serializer resolvable
        produit une signature absente de la base -> job rouge."""
        log = _line("backend/django_core/apps/crm/views.py:42", "Error",
                    "BrandNewUnresolvableView", GUESS)
        found = cos.parse_log(log)
        self.assertTrue(found - self.baseline)

    def test_a_new_operationid_collision_is_reported(self):
        log = ('Warning: operationId "brand_new_collision_retrieve" has collisions '
               "[('/api/x/', 'get'), ('/api/x/{id}/', 'get')]. resolving with "
               "numeral suffixes.")
        self.assertTrue(cos.parse_log(log) - self.baseline)

    def test_an_already_baselined_finding_is_not_reported(self):
        sample = sorted(self.baseline)[0]
        severity, identity, msg = sample.split("|", 2)
        log = _line("some/file.py:1", severity, identity, msg)
        self.assertFalse(cos.parse_log(log) - self.baseline)


class InventoryTests(unittest.TestCase):
    SCHEMA = """
openapi: 3.0.3
info:
  title: T
  version: '1.0.0'
paths:
  /b/:
    get:
      operationId: b_list
  /a/:
    post:
      operationId: a_create
    get:
      operationId: a_list
components:
  schemas:
    Zeta: {}
    Alpha: {}
  securitySchemes:
    cookieJWT: {}
"""

    def _inventory(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False,
                                         encoding="utf-8") as fh:
            fh.write(self.SCHEMA)
            path = Path(fh.name)
        try:
            return cos.build_inventory(path)
        finally:
            path.unlink()

    def test_operations_are_sorted_and_complete(self):
        text = self._inventory()
        ops = [ln for ln in text.splitlines() if ln.startswith("- ") and " -> " in ln]
        self.assertEqual(ops, [
            "- get /a/ -> a_list",
            "- post /a/ -> a_create",
            "- get /b/ -> b_list",
        ])

    def test_counts_and_components_are_reported(self):
        text = self._inventory()
        self.assertIn("counts: {paths: 2, operations: 3, components: 2}", text)
        self.assertIn("- cookieJWT", text)
        self.assertIn("components:\n- Alpha\n- Zeta\n", text)

    def test_inventory_is_deterministic(self):
        self.assertEqual(self._inventory(), self._inventory())

    def test_committed_snapshot_matches_the_inventory_format(self):
        snapshot = cos.SNAPSHOT_PATH
        self.assertTrue(snapshot.is_file(), f"{snapshot} manquant")
        text = snapshot.read_text(encoding="utf-8")
        self.assertIn("operations:", text)
        self.assertIn("securitySchemes:", text)
        self.assertTrue(cos._operation_lines(text))


if __name__ == "__main__":
    unittest.main()
