"""AANA6 — l'agent SQL ne retombe JAMAIS sur la connexion proprietaire en
production (C-AANA-002).

Avant : `config.py` retombait sur DATABASE_URL quand SQL_AGENT_DB_USER etait
vide ; en local l'agent tournait sous `erp_user` (rolsuper=t, rolbypassrls=t).
Maintenant, DEBUG off + SQL_AGENT_DB_USER absent => agent DESACTIVE : la route
repond 503 avec un message qui NOMME la variable, et le moteur de l'agent
refuse de se creer. En developpement (DEBUG on) le repli reste, avec un
avertissement.

La configuration est rechargee (importlib.reload) sous un environnement
controle, puis restauree. Seul le LLM est simule ; aucune base n'est requise.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
"""
import importlib
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._import_optionnel import verifier_import_optionnel  # noqa: E402

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.endpoints import sql_agent as _ep
    from app.core import config as _config
    from app.core import database as _db
    _ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    _config = None
    _ERR = exc
    verifier_import_optionnel(exc)


def _env(debug, agent_user):
    env = {
        "DJANGO_DEBUG": "True" if debug else "False",
        "FASTAPI_SECRET_KEY": "une-cle-de-production-assez-longue",
        "DB_USER": "erp_user",
        "DB_PASSWORD": "pw",
        "DB_HOST": "db",
        "DB_NAME": "erp_db",
    }
    if agent_user is not None:
        env["SQL_AGENT_DB_USER"] = agent_user
        env["SQL_AGENT_DB_PASSWORD"] = "agentpw"
    return env


@unittest.skipIf(_config is None, f"app.core non importable: {_ERR}")
class ConfigAgentSqlTests(unittest.TestCase):

    def _reload(self, debug, agent_user):
        keys = ("DJANGO_DEBUG", "FASTAPI_SECRET_KEY", "DB_USER", "DB_PASSWORD",
                "DB_HOST", "DB_NAME", "SQL_AGENT_DB_USER",
                "SQL_AGENT_DB_PASSWORD")
        patched = {k: v for k, v in os.environ.items() if k not in keys}
        patched.update(_env(debug, agent_user))
        with mock.patch.dict(os.environ, patched, clear=True):
            importlib.reload(_config)
        # Restaure la configuration du processus apres le test.
        self.addCleanup(importlib.reload, _config)

    def _client(self):
        from app.core.security import get_raw_token, verify_token

        app = FastAPI()
        app.include_router(_ep.router, prefix="/sql-agent")
        app.dependency_overrides[verify_token] = lambda: {
            "user_id": 301, "company_id": 7, "role": "admin",
        }
        app.dependency_overrides[get_raw_token] = lambda: "jwt-xyz"
        return TestClient(app)

    def test_prod_sans_role_dedie_refuse(self):
        self._reload(debug=False, agent_user=None)
        # Plus aucun repli sur la connexion proprietaire.
        self.assertNotEqual(_config.SQL_AGENT_DATABASE_URL,
                            _config.DATABASE_URL)
        self.assertNotIn("erp_user", _config.SQL_AGENT_DATABASE_URL)
        self.assertIn("SQL_AGENT_DB_USER", _config.SQL_AGENT_DISABLED_REASON)
        # Le moteur de l'agent refuse de se creer.
        with self.assertRaises(_db.SqlAgentDisabledError):
            _db.create_sql_agent_engine()
        # La route repond 503 en nommant la variable, sans appeler le LLM.
        calls = []

        async def fake_query(**kwargs):
            calls.append(kwargs)
            return {"answer": "ok", "sql_query": "", "data": None}

        with mock.patch.object(_ep.sql_agent_service, "query", fake_query):
            r = self._client().post("/sql-agent/query",
                                    json={"question": "combien de devis ?"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("SQL_AGENT_DB_USER", r.json()["detail"])
        self.assertEqual(calls, [])

    def test_prod_avec_role_dedie_utilise_le_role(self):
        self._reload(debug=False, agent_user="erp_sql_agent")
        self.assertEqual(_config.SQL_AGENT_DISABLED_REASON, "")
        self.assertIn("erp_sql_agent:", _config.SQL_AGENT_DATABASE_URL)
        engine = _db.create_sql_agent_engine()  # aucune connexion ouverte
        self.assertEqual(engine.url.username, "erp_sql_agent")

    def test_dev_sans_role_dedie_avertit(self):
        with self.assertLogs("app.core.config", level="WARNING") as logs:
            self._reload(debug=True, agent_user=None)
        self.assertTrue(any("SQL_AGENT_DB_USER" in m for m in logs.output))
        self.assertEqual(_config.SQL_AGENT_DATABASE_URL, _config.DATABASE_URL)
        self.assertEqual(_config.SQL_AGENT_DISABLED_REASON, "")


if __name__ == "__main__":
    unittest.main()
