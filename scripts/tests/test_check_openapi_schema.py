"""Tests YAPIC6 — scripts/check_openapi_schema.py.

Pure stdlib (unittest), no Django, no schema generation. Run:
    python -m unittest scripts.tests.test_check_openapi_schema -v

Prouve le critere « introduire volontairement un serializer ambigu fait rougir
le job » SANS payer les ~3 min de generation du schema : le ratchet est teste
sur des journaux drf-spectacular synthetiques + la vraie base de reference
versionnee.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


class DeriveInstantaneTests(unittest.TestCase):
    """PACT6 — la derive de docs/openapi-schema.yml est BLOQUANTE.

    Le cas reel : l'instantane a ete regenere le 31/07, le module Appels
    d'offres a fusionne le 02/08, et le fichier de contrat n'a pas bouge d'une
    ligne (29 ressources absentes, dont 21 dans apps/ao). Ces tests prouvent
    que la meme situation rougit desormais, et que le message NOMME les routes.
    """

    ANCIEN = ("counts: {paths: 1, operations: 1, components: 1}\n"
              "operations:\n"
              "- get /api/django/crm/leads/ -> crm_leads_list\n"
              "components:\n"
              "- Lead\n")
    NOUVEAU = ("counts: {paths: 2, operations: 3, components: 2}\n"
               "operations:\n"
               "- get /api/django/ao/appels-offres/ -> ao_appels_offres_list\n"
               "- get /api/django/crm/leads/ -> crm_leads_list\n"
               "components:\n"
               "- AppelOffre\n"
               "- Lead\n")

    def test_instantane_a_jour_ne_derive_pas(self):
        self.assertIsNone(cos.derive_instantane(self.ANCIEN, self.ANCIEN))

    def test_route_ajoutee_sans_regeneration_est_une_derive(self):
        derive = cos.derive_instantane(self.ANCIEN, self.NOUVEAU)
        self.assertIsNotNone(derive)
        self.assertEqual(
            derive["operations_manquantes"],
            ["- get /api/django/ao/appels-offres/ -> ao_appels_offres_list"])
        self.assertEqual(derive["operations_en_trop"], [])
        self.assertEqual(derive["composants_manquants"], ["- AppelOffre"])

    def test_route_retiree_du_code_est_une_derive(self):
        derive = cos.derive_instantane(self.NOUVEAU, self.ANCIEN)
        self.assertIsNotNone(derive)
        self.assertEqual(
            derive["operations_en_trop"],
            ["- get /api/django/ao/appels-offres/ -> ao_appels_offres_list"])
        self.assertEqual(derive["operations_manquantes"], [])

    def test_derive_d_entete_seule_est_detectee(self):
        # Un compteur qui bouge sans qu'aucune operation ne change : l'instantane
        # reste FAUX, donc rouge — mais le message le dit explicitement.
        modifie = self.ANCIEN.replace("paths: 1", "paths: 2")
        derive = cos.derive_instantane(self.ANCIEN, modifie)
        self.assertIsNotNone(derive)
        self.assertEqual(derive["operations_manquantes"], [])
        self.assertEqual(derive["operations_en_trop"], [])

    def test_le_message_nomme_les_routes_et_la_commande_de_regeneration(self):
        derive = cos.derive_instantane(self.ANCIEN, self.NOUVEAU)
        flux = io.StringIO()
        with redirect_stdout(flux):
            cos.rapporter_derive(derive, "docs/openapi-schema.yml")
        texte = flux.getvalue()
        self.assertIn("ao_appels_offres_list", texte)
        self.assertIn("ECHEC", texte)
        self.assertIn(cos.REGEN_COMMAND, texte)
        self.assertIn("02/08", texte)

    def _main_avec(self, instantane_versionne, inventaire_genere, argv):
        """Joue `main()` sans generer le schema : seul le verdict est teste."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snapshot = base / "docs" / "openapi-schema.yml"
            if instantane_versionne is not None:
                snapshot.parent.mkdir(parents=True)
                snapshot.write_text(instantane_versionne, encoding="utf-8", newline="\n")
            anciens = (cos.ROOT, cos.SNAPSHOT_PATH, cos.generate,
                       cos.build_inventory, sys.argv)
            cos.ROOT, cos.SNAPSHOT_PATH = base, snapshot
            cos.generate = lambda target: ""
            cos.build_inventory = lambda target: inventaire_genere
            sys.argv = ["check_openapi_schema.py"] + argv
            flux = io.StringIO()
            try:
                with redirect_stdout(flux):
                    code = cos.main()
            finally:
                (cos.ROOT, cos.SNAPSHOT_PATH, cos.generate,
                 cos.build_inventory, sys.argv) = anciens
            texte = flux.getvalue()
            gele = snapshot.read_text(encoding="utf-8") if snapshot.is_file() else None
            return code, texte, gele

    def test_une_route_ajoutee_sans_regeneration_rend_le_controle_ROUGE(self):
        # LE critere de PACT6. Avant, ce meme cas imprimait « Info : ... » et
        # renvoyait 0 — c'est ainsi que le module AO est passe en production
        # sans que docs/openapi-schema.yml bouge.
        code, texte, _ = self._main_avec(self.ANCIEN, self.NOUVEAU, [])
        self.assertEqual(code, 1)
        self.assertIn("ECHEC", texte)
        self.assertIn("ao_appels_offres_list", texte)
        self.assertIn(cos.REGEN_COMMAND, texte)

    def test_instantane_a_jour_reste_VERT(self):
        code, texte, _ = self._main_avec(self.ANCIEN, self.ANCIEN, [])
        self.assertEqual(code, 0)
        self.assertNotIn("ECHEC", texte)

    def test_instantane_absent_est_ROUGE(self):
        code, texte, _ = self._main_avec(None, self.NOUVEAU, [])
        self.assertEqual(code, 1)
        self.assertIn(cos.REGEN_COMMAND, texte)

    def test_write_regenere_et_repasse_au_vert(self):
        code, _, gele = self._main_avec(self.ANCIEN, self.NOUVEAU, ["--write"])
        self.assertEqual(code, 0)
        self.assertEqual(gele, self.NOUVEAU)

    def test_composants_lus_depuis_la_queue_de_l_instantane(self):
        # `_component_lines` ne doit pas confondre une operation avec un
        # composant : seule la section finale `components:` compte.
        self.assertEqual(cos._component_lines(self.NOUVEAU),
                         {"- AppelOffre", "- Lead"})


if __name__ == "__main__":
    unittest.main()
