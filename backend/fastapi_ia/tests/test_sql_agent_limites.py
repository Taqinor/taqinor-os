"""AANA5 — Bornes de l'agent SQL (C-AANA-034).

  - `question` limitee a 2 000 caracteres : 422 au-dela (avant tout appel LLM) ;
  - limiteur de debit Redis (fenetre glissante, fail-closed comme l'OCR) :
    429 au-dela du plafond, 503 si Redis est injoignable ;
  - `statement_timeout = 15 s` sur le moteur DEDIE de l'agent (un `pg_sleep`
    ou une jointure explosive ne tient plus une connexion indefiniment), et
    l'agent passe bien par ce moteur.

Seul le LLM (frontiere externe) et Redis (infrastructure du limiteur) sont
simules ; jamais la base ni le garde SQL. Le test Postgres se saute sans base
de test configuree (DB_HOST absent), comme dans test_sql_security.py.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
"""
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.endpoints import sql_agent as _ep
    from app.core import database as _db
    _ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    _ep = None
    _db = None
    _ERR = exc


class _FakeRedisPipeline:
    def __init__(self, store):
        self._store = store
        self._ops = []

    def zremrangebyscore(self, key, lo, hi):
        self._ops.append(("zrem", key, lo, hi))
        return self

    def zadd(self, key, mapping):
        self._ops.append(("zadd", key, mapping))
        return self

    def zcard(self, key):
        self._ops.append(("zcard", key))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    def execute(self):
        out = []
        for op in self._ops:
            if op[0] == "zrem":
                _, key, lo, hi = op
                zset = self._store.setdefault(key, {})
                for member in [m for m, s in zset.items() if lo <= s <= hi]:
                    del zset[member]
                out.append(None)
            elif op[0] == "zadd":
                self._store.setdefault(op[1], {}).update(op[2])
                out.append(1)
            elif op[0] == "zcard":
                out.append(len(self._store.get(op[1], {})))
            else:
                out.append(True)
        self._ops = []
        return out


class _FakeRedis:
    """Zset en memoire : juste ce que le limiteur utilise."""

    def __init__(self):
        self.store = {}

    def pipeline(self):
        return _FakeRedisPipeline(self.store)


class _DeadRedis:
    def pipeline(self):
        raise ConnectionError("redis injoignable")


@unittest.skipIf(_ep is None, f"endpoint sql_agent non importable: {_ERR}")
class SqlAgentLimitesTests(unittest.TestCase):

    def _client(self, user_id):
        from app.core.security import get_raw_token, verify_token

        app = FastAPI()
        app.include_router(_ep.router, prefix="/sql-agent")
        app.dependency_overrides[verify_token] = lambda: {
            "user_id": user_id, "company_id": 7, "role": "admin",
            "is_superuser": False,
        }
        app.dependency_overrides[get_raw_token] = lambda: "jwt-xyz"
        return TestClient(app)

    def _patch_llm(self):
        """Simule l'agent (LLM) : compte les appels, ne touche rien."""
        calls = []

        async def fake_query(question, user_id=None, company_id=None,
                             action_ctx=None):
            calls.append(question)
            return {"answer": "ok", "sql_query": "", "data": None}

        patcher = mock.patch.object(_ep.sql_agent_service, "query", fake_query)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    def _patch_redis(self, fake):
        patcher = mock.patch.object(_db, "get_rate_limit_redis", lambda: fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_question_trop_longue_422(self):
        calls = self._patch_llm()
        self._patch_redis(_FakeRedis())
        client = self._client(101)
        r = client.post("/sql-agent/query", json={"question": "x" * 3000})
        self.assertEqual(r.status_code, 422)
        r = client.post("/sql-agent/query",
                        json={"question": "x" * (1024 * 1024)})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(calls, [], "la question trop longue a atteint le LLM")
        # A la borne exacte : acceptee.
        r = client.post("/sql-agent/query", json={"question": "x" * 2000})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(calls), 1)

    def test_debit_limite_429(self):
        calls = self._patch_llm()
        self._patch_redis(_FakeRedis())
        client = self._client(102)
        codes = [
            client.post("/sql-agent/query",
                        json={"question": "combien de devis ?"}).status_code
            for _ in range(30)
        ]
        self.assertEqual(codes[:_ep.SQL_AGENT_RATE_LIMIT_MAX],
                         [200] * _ep.SQL_AGENT_RATE_LIMIT_MAX)
        self.assertIn(429, codes)
        self.assertEqual(set(codes[_ep.SQL_AGENT_RATE_LIMIT_MAX:]), {429})
        self.assertEqual(len(calls), _ep.SQL_AGENT_RATE_LIMIT_MAX)
        self.assertLess(_ep.SQL_AGENT_RATE_LIMIT_MAX, 30)
        self.assertLessEqual(_ep.SQL_AGENT_RATE_LIMIT_WINDOW, 3600)

    def test_debit_par_utilisateur(self):
        self._patch_llm()
        fake = _FakeRedis()
        self._patch_redis(fake)
        a, b = self._client(103), self._client(104)
        for _ in range(_ep.SQL_AGENT_RATE_LIMIT_MAX + 1):
            a.post("/sql-agent/query", json={"question": "q"})
        self.assertEqual(
            b.post("/sql-agent/query", json={"question": "q"}).status_code,
            200)

    def test_redis_injoignable_503_fail_closed(self):
        calls = self._patch_llm()
        self._patch_redis(_DeadRedis())
        r = self._client(105).post("/sql-agent/query",
                                   json={"question": "q"})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(calls, [])


@unittest.skipIf(_db is None, f"app.core.database non importable: {_ERR}")
class SqlAgentStatementTimeoutTests(unittest.TestCase):

    def test_moteur_agent_porte_statement_timeout_15s(self):
        self.assertEqual(_db.SQL_AGENT_STATEMENT_TIMEOUT_MS, 15000)
        options = _db.sql_agent_engine_args()["connect_args"]["options"]
        self.assertIn("statement_timeout=15000", options)

    def test_agent_passe_par_le_moteur_dedie(self):
        """L'agent ne cree plus son moteur depuis une URL nue : il passe par
        `create_sql_agent_engine` (donc par le statement_timeout)."""
        from app.services import sql_agent_service as svc

        class _Sentinel(Exception):
            pass

        def _boom():
            raise _Sentinel()

        service = svc.SQLAgentService()
        with mock.patch.object(_db, "create_sql_agent_engine", _boom), \
                mock.patch.object(service, "_load_history", lambda uid: []), \
                mock.patch.object(service, "_get_relevant_tables",
                                  lambda q: ["crm_client"]):
            with self.assertRaises(_Sentinel):
                service._run_agent("combien de clients ?", 7, 1, None)

    def test_statement_timeout_effectif_sur_postgres(self):
        if not os.environ.get("DB_HOST"):
            self.skipTest("Postgres de test non configure (DB_HOST absent).")
        from sqlalchemy import text
        try:
            engine = _db.create_sql_agent_engine()
            with engine.connect() as conn:
                value = conn.execute(text("SHOW statement_timeout")).scalar()
        except Exception as exc:  # pragma: no cover - base injoignable
            self.skipTest(f"Postgres de test injoignable : {exc}")
        self.assertEqual(value, "15s")


if __name__ == "__main__":
    unittest.main()
