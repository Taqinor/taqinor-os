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

from unittest import mock

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

try:
    from fastapi import FastAPI as _FastAPI
    from fastapi.testclient import TestClient as _TestClient
    _HAS_CLIENT = True
except Exception:  # pragma: no cover - starlette/httpx absents
    _FastAPI = None
    _TestClient = None
    _HAS_CLIENT = False

from app.services import action_tools as _at  # noqa: E402

# Catalogue de test (mime apps/agent/registry.py).
_CAT_PROPOSAL_PDF = {
    "key": "ventes.devis.proposal_pdf",
    "label": "Générer le PDF",
    "description": "Génère le PDF client.",
    "endpoint": "/api/django/ventes/devis/{id}/proposal/",
    "method": "GET",
    "inputs": {"type": "object", "properties": {"id": {"type": "integer"}},
               "required": ["id"]},
    "risk": "outward",
    "confirm_summary": "Produire le PDF de devis destiné au client.",
}
_CAT_LEAD_LIST = {
    "key": "crm.lead.list",
    "label": "Lister les leads",
    "description": "Liste les leads.",
    "endpoint": "/api/django/crm/leads/",
    "method": "GET",
    "inputs": {"type": "object", "properties": {}},
    "risk": "internal",
    "confirm_summary": None,
}
_FULL_CATALOGUE = [_CAT_PROPOSAL_PDF, _CAT_LEAD_LIST]


class _FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, ex=None):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)


def _ctx():
    from app.services.action_tools import ActionContext
    return ActionContext(company_id=7, role="admin", permissions=[],
                         token="jwt-xyz")


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


# ── AG2 (surfacage) — proposal / result + confirm_token sur /query ────────────


@unittest.skipUnless(_OK, f"sql_agent endpoint indisponible: {_ERR}")
class SQLResponseAg2FieldsTests(unittest.TestCase):
    """Les champs AG2 sont OPTIONNELS et None par defaut (callers inchanges)."""

    def test_proposal_and_result_default_null(self):
        resp = _ep.SQLResponse(answer="ok")
        self.assertIsNone(resp.proposal)
        self.assertIsNone(resp.result)

    def test_fields_present_in_model(self):
        self.assertIn("proposal", _ep.SQLResponse.model_fields)
        self.assertIn("result", _ep.SQLResponse.model_fields)


@unittest.skipUnless(_OK and _HAS_CLIENT,
                     f"fastapi TestClient indisponible: {_ERR}")
class QueryConfirmLoopTests(unittest.TestCase):
    """Boucle bout-en-bout : /query remonte proposal.confirm_token, ce jeton est
    accepte par /confirm, et une action interne remonte result."""

    def setUp(self):
        from app.core.security import get_raw_token, verify_token

        app = _FastAPI()
        app.include_router(_ep.router, prefix="/sql-agent")
        app.dependency_overrides[verify_token] = lambda: {
            "user_id": 1, "company_id": 7, "role": "admin",
            "permissions": [], "is_superuser": False,
        }
        app.dependency_overrides[get_raw_token] = lambda: "jwt-xyz"
        self.client = _TestClient(app)

        self._sec = mock.patch.object(_at, "ACTION_PROPOSAL_SECRET", "sig-secret")
        self._sec.start()
        self.addCleanup(self._sec.stop)
        self.fake_redis = _FakeRedis()
        self._rds = mock.patch.object(_at, "_proposal_redis",
                                      lambda: self.fake_redis)
        self._rds.start()
        self.addCleanup(self._rds.stop)

    @staticmethod
    def _service_payload(collector):
        from app.services.sql_agent_service import SQLAgentService
        return {
            "answer": "ok", "sql_query": "", "data": None,
            "action_performed": bool(collector),
            "proposal": SQLAgentService._build_proposal_payload(collector),
            "result": SQLAgentService._build_result_payload(collector),
        }

    def test_outward_query_then_confirm(self):
        async def fake_query(question, user_id=None, company_id=None,
                             action_ctx=None):
            collector = []
            with mock.patch.object(
                    _at, "_django_call",
                    lambda *a, **k: (_ for _ in ()).throw(
                        AssertionError("outward ne s'execute pas"))):
                _at.run_catalogue_action(_ctx(), _CAT_PROPOSAL_PDF, {"id": 9},
                                         collector)
            return self._service_payload(collector)

        with mock.patch.object(_ep.sql_agent_service, "query", fake_query):
            r = self.client.post("/sql-agent/query",
                                 json={"question": "génère le PDF du devis 9"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsNone(body["result"])
        prop = body["proposal"]
        self.assertIsNotNone(prop)
        self.assertEqual(prop["action_key"], "ventes.devis.proposal_pdf")
        self.assertEqual(prop["inputs"], {"id": 9})
        self.assertTrue(prop["confirm_token"])

        captured = {}

        def fake_call(ctx, path, method="POST", payload=None):
            captured["path"] = path
            return {"ok": True, "status": 200, "data": {"pdf": "ok"}}

        with mock.patch.object(_at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(_at, "_django_call", fake_call):
            c = self.client.post("/sql-agent/confirm",
                                 json={"token": prop["confirm_token"]})
        self.assertEqual(c.status_code, 200)
        cbody = c.json()
        self.assertTrue(cbody["ok"])
        self.assertEqual(cbody["action_key"], "ventes.devis.proposal_pdf")
        self.assertEqual(captured["path"],
                         "/api/django/ventes/devis/9/proposal/")

    def test_internal_query_surfaces_result(self):
        async def fake_query(question, user_id=None, company_id=None,
                             action_ctx=None):
            collector = []
            with mock.patch.object(
                    _at, "_django_call",
                    lambda ctx, path, method="POST", payload=None:
                    {"ok": True, "status": 200,
                     "data": {"reference": "SAV-1", "wa_url": "https://wa/x"}}):
                _at.run_catalogue_action(_ctx(), _CAT_LEAD_LIST, {}, collector)
            return self._service_payload(collector)

        with mock.patch.object(_ep.sql_agent_service, "query", fake_query):
            r = self.client.post("/sql-agent/query",
                                 json={"question": "liste les leads"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsNone(body["proposal"])
        result = body["result"]
        self.assertIsNotNone(result)
        self.assertEqual(result["action_key"], "crm.lead.list")
        self.assertEqual(result["reference"], "SAV-1")
        self.assertEqual(result["wa_url"], "https://wa/x")

    def test_query_without_action_null_fields(self):
        async def fake_query(question, user_id=None, company_id=None,
                             action_ctx=None):
            return {"answer": "5 produits.", "sql_query": "", "data": None,
                    "action_performed": False, "proposal": None,
                    "result": None}

        with mock.patch.object(_ep.sql_agent_service, "query", fake_query):
            r = self.client.post("/sql-agent/query",
                                 json={"question": "combien de produits ?"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIsNone(body["proposal"])
        self.assertIsNone(body["result"])


if __name__ == "__main__":
    unittest.main()
