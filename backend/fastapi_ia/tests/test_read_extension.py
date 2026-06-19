"""
Tests de l'extension LECTURE de l'agent (N86) : les nouvelles tables
apres-vente / chantiers / parc / maintenance sont dans l'allowlist, portent
toutes le filtrage company_id, et sont decrites pour pgvector.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests

Le module sql_agent_service importe langchain_community au runtime mais PAS au
chargement du module (imports differes dans les methodes), donc l'import du
module pour inspecter les constantes ne requiert pas les dependances IA. Si une
dependance de chargement manque, le test se saute proprement.
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

_NEW_TABLES = [
    "installations_installation",
    "installations_intervention",
    "sav_equipement",
    "sav_ticket",
    "sav_contratmaintenance",
]


@unittest.skipIf(svc is None, f"sql_agent_service non importable: {_IMPORT_ERR}")
class ReadExtensionTests(unittest.TestCase):
    def test_new_tables_in_allowlist(self):
        for t in _NEW_TABLES:
            self.assertIn(t, svc._ALLOWED_TABLES, t)

    def test_new_tables_company_scoped(self):
        # Toutes ces tables portent company_id => filtrage obligatoire.
        for t in _NEW_TABLES:
            self.assertIn(t, svc._TABLES_WITH_COMPANY_ID, t)

    def test_new_tables_described(self):
        for t in _NEW_TABLES:
            self.assertIn(t, svc._TABLE_DESCRIPTIONS, t)
            self.assertTrue(svc._TABLE_DESCRIPTIONS[t].strip(), t)

    def test_company_filter_injected_on_new_table(self):
        sql = "SELECT reference FROM installations_installation"
        out = svc._inject_company_filter(sql, 42)
        self.assertIn("company_id = 42", out)

    def test_margin_restriction_text_present(self):
        # La restriction marge existe et cible prix_achat.
        self.assertIn("prix_achat", svc._MARGIN_RESTRICTION)


if __name__ == "__main__":
    unittest.main()
