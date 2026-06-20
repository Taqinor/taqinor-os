"""ERR44 / ERR84 — Endpoint de l'agent SQL.

  - ERR44 : un company_id absent ou nul (=0) DESACTIVERAIT le scoping tenant.
    L'endpoint doit exiger un company_id present et non nul, et renvoyer 403
    comme l'OCR sinon.
  - ERR84 : le SQL genere (vrais noms de tables) n'est jamais renvoye au client.
    Le champ SQLResponse.sql_query est present (contrat) mais vide par defaut.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests

L'endpoint importe fastapi ; si absent (env leger), les tests se sautent.
"""
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.api.endpoints import sql_agent as _ep
    from fastapi import HTTPException as _HTTPException
    _OK = True
    _ERR = None
except Exception as exc:  # pragma: no cover - fastapi absent
    _ep = None
    _HTTPException = None
    _OK = False
    _ERR = exc


@unittest.skipUnless(_OK, f"sql_agent endpoint indisponible: {_ERR}")
class RequireCompanyIdTests(unittest.TestCase):
    def test_missing_company_id_403(self):
        with self.assertRaises(_HTTPException) as cm:
            _ep._require_company_id({"user_id": 1})
        self.assertEqual(cm.exception.status_code, 403)

    def test_zero_company_id_403(self):
        with self.assertRaises(_HTTPException) as cm:
            _ep._require_company_id({"user_id": 1, "company_id": 0})
        self.assertEqual(cm.exception.status_code, 403)

    def test_non_numeric_company_id_403(self):
        with self.assertRaises(_HTTPException) as cm:
            _ep._require_company_id({"company_id": "abc"})
        self.assertEqual(cm.exception.status_code, 403)

    def test_valid_company_id_returns_int(self):
        self.assertEqual(
            _ep._require_company_id({"company_id": 7}), 7)
        self.assertEqual(
            _ep._require_company_id({"company_id": "7"}), 7)


@unittest.skipUnless(_OK, f"sql_agent endpoint indisponible: {_ERR}")
class SqlNotDisclosedTests(unittest.TestCase):
    def test_sql_query_defaults_empty(self):
        resp = _ep.SQLResponse(answer="ok")
        self.assertEqual(resp.sql_query, "")

    def test_sql_query_field_present_in_model(self):
        # Le contrat conserve le champ (frontend) meme s'il est vide.
        self.assertIn("sql_query", _ep.SQLResponse.model_fields)


if __name__ == "__main__":
    unittest.main()
