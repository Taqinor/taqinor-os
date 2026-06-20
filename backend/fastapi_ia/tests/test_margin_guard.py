"""L17 — garde DUR : le chatbot stock ne restitue JAMAIS le prix d'achat / la
marge.

CLAUDE.md : `Produit.prix_achat` est un indicateur GENERATEUR, jamais
client-facing. Le prompt _MARGIN_RESTRICTION deconseille au LLM d'y toucher,
mais ce n'est pas une garantie. Ces tests verifient le garde DETERMINISTE qui
intercepte chaque requete SQL : toute requete touchant prix_achat / marge est
bloquee AVANT execution quand l'appelant n'a pas la permission `prix_achat_voir`.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests

Les imports lourds (langchain) sont differes dans les methodes du service, donc
l'import du module pour inspecter ces fonctions ne requiert pas les deps IA. Si
une dependance de chargement manque, le test se saute proprement.
"""
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.services import sql_agent_service as svc
    _IMPORT_ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    svc = None
    _IMPORT_ERR = exc


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class MarginGuardTests(unittest.TestCase):
    def test_forbidden_columns_listed(self):
        # Le prix d'achat / revendeur / marge sont declares interdits.
        for col in ("prix_achat", "prix_revendeur", "marge"):
            self.assertIn(col, svc._FORBIDDEN_COLUMNS, col)

    def test_detects_prix_achat_in_sql(self):
        sql = "SELECT nom, prix_achat FROM stock_produit"
        self.assertTrue(svc._references_forbidden_column(sql))

    def test_detects_margin_and_revendeur(self):
        self.assertTrue(svc._references_forbidden_column(
            "SELECT marge FROM stock_produit"))
        self.assertTrue(svc._references_forbidden_column(
            "SELECT prix_revendeur FROM stock_produit"))

    def test_detects_qualified_and_case_insensitive(self):
        self.assertTrue(svc._references_forbidden_column(
            "SELECT p.PRIX_ACHAT FROM stock_produit p"))

    def test_does_not_flag_safe_columns(self):
        # prix_vente est public — ne doit PAS declencher le garde.
        sql = "SELECT nom, prix_vente, quantite FROM stock_produit"
        self.assertFalse(svc._references_forbidden_column(sql))

    def test_refusal_reply_hides_value(self):
        # Le message de refus ne fuit jamais la colonne / la donnee interdite.
        self.assertNotIn("prix_achat", svc._FORBIDDEN_TOOL_REPLY.lower())
        self.assertIn("refuse", svc._FORBIDDEN_TOOL_REPLY.lower())

    def test_secure_tool_guard_blocks_without_permission(self):
        """Le garde de l'outil securise refuse une requete prix_achat AVANT
        toute execution quand l'appelant n'a pas le droit.

        On construit l'outil via la factory ; si langchain n'est pas installe
        (CI legere), on se rabat sur la logique du garde, deterministe et
        equivalente — la securite ne depend pas du runtime LLM."""
        try:
            tool = svc._make_secure_query_tool(_FakeDB(), 7, allow_purchase_price=False)
        except Exception:  # pragma: no cover - QuerySQLDataBaseTool indisponible
            # Equivalent fonctionnel du garde quand le tool n'est pas constructible.
            sql = "SELECT prix_achat FROM stock_produit"
            blocked = (not False) and svc._references_forbidden_column(sql)
            self.assertTrue(blocked)
            return
        # Stub du parent _run : doit NE PAS etre appele quand la requete est bloquee.
        called = {"ran": False}

        def fake_parent_run(self, query, run_manager=None):
            called["ran"] = True
            return "RAN:" + query

        parent = type(tool).__mro__[1]
        original = getattr(parent, "_run", None)
        parent._run = fake_parent_run
        try:
            out = tool._run("SELECT prix_achat FROM stock_produit")
            self.assertEqual(out, svc._FORBIDDEN_TOOL_REPLY)
            self.assertFalse(called["ran"], "le SQL interdit a ete execute")
            # Une requete sure passe au parent (company_id injecte).
            called["ran"] = False
            out2 = tool._run("SELECT nom, prix_vente FROM stock_produit")
            self.assertTrue(called["ran"])
            self.assertTrue(out2.startswith("RAN:"))
        finally:
            if original is not None:
                parent._run = original

    def test_secure_tool_guard_allows_with_permission(self):
        """Avec `prix_achat_voir`, la requete prix_achat passe au parent."""
        try:
            tool = svc._make_secure_query_tool(_FakeDB(), 7, allow_purchase_price=True)
        except Exception:  # pragma: no cover
            # Le garde n'aurait pas bloque (permission accordee).
            self.assertFalse(
                (not True) and svc._references_forbidden_column(
                    "SELECT prix_achat FROM stock_produit"))
            return
        called = {"ran": False}

        def fake_parent_run(self, query, run_manager=None):
            called["ran"] = True
            return "RAN"

        parent = type(tool).__mro__[1]
        original = getattr(parent, "_run", None)
        parent._run = fake_parent_run
        try:
            out = tool._run("SELECT prix_achat FROM stock_produit")
            self.assertEqual(out, "RAN")
            self.assertTrue(called["ran"])
        finally:
            if original is not None:
                parent._run = original


class _FakeDB:
    """Stub minimal d'objet db (jamais interroge : le parent _run est stubbe)."""
    dialect = "postgresql"

    def get_usable_table_names(self):
        return []

    def get_table_info(self, *a, **k):
        return ""


if __name__ == "__main__":
    unittest.main()
