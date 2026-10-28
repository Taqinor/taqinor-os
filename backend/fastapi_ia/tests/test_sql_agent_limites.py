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

from tests._import_optionnel import verifier_import_optionnel  # noqa: E402 — après sys.path/setup() (D-ENF22)

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
    verifier_import_optionnel(exc)


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
        # AANA8 — /query lit les permissions par /auth/me/ de Django (service
        # HTTP externe) : reponse simulee, sinon chaque requete attendrait le
        # reseau et la rafale sortirait de la fenetre du limiteur.
        from app.services import action_tools as _at
        patcher = mock.patch.object(
            _at, "_django_call",
            lambda ctx, path, method="POST", payload=None: {
                "ok": True, "status": 200, "data": {"permissions": []}})
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


def _llm_factices():
    """AIC4 — un client Claude qui REFUSE (solde nul) et un client Groq qui
    repond, construits par le vrai `_run_agent` (aucun mock de l'executeur)."""
    import anthropic
    import httpx
    from langchain_core.language_models.fake_chat_models import (
        GenericFakeChatModel,
    )
    from langchain_core.messages import AIMessage

    class _Fake(GenericFakeChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    class _ClaudeRefuse(_Fake):
        erreur: Exception = None

        def _generate(self, *args, **kwargs):
            raise self.erreur

    def credit_nul():
        return anthropic.BadRequestError(
            "Your credit balance is too low to access the Anthropic API.",
            response=httpx.Response(400, request=httpx.Request(
                "POST", "https://api.anthropic.com/v1/messages")),
            body=None)

    def groq():
        return _Fake(messages=iter([AIMessage(content="Reponse du repli.")]))

    return _ClaudeRefuse, credit_nul, groq


class SqlAgentRepliAic4Tests(unittest.TestCase):
    """AIC4 — Claude refuse (credits, quota, 5xx, cle) => UN rejeu sur Groq,
    `repli` vrai ; une erreur d'outil n'est jamais un motif de repli."""

    def setUp(self):
        try:
            import anthropic  # noqa: F401
            from sqlalchemy import create_engine, text
        except ModuleNotFoundError as exc:  # pragma: no cover
            self.skipTest(str(exc))
        from app.services import sql_agent_service as svc
        self.svc = svc
        from sqlalchemy.pool import StaticPool
        # Base en memoire partagee entre threads (query -> asyncio.to_thread).
        engine = create_engine("sqlite://", poolclass=StaticPool,
                               connect_args={"check_same_thread": False})
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE crm_client (id INTEGER, nom TEXT)"))
        self.service = svc.SQLAgentService()
        for cible, valeur in (
            (_db, {"create_sql_agent_engine": lambda: engine}),
            (self.service, {"_load_history": lambda uid: [],
                            "_save_history": lambda *a, **k: None,
                            "_get_relevant_tables": lambda q: ["crm_client"]}),
            (svc, {"SQL_AGENT_PROVIDER": "claude",
                   "SQL_AGENT_FALLBACK_PROVIDER": "groq"}),
        ):
            p = mock.patch.multiple(cible, **valeur)
            p.start()
            self.addCleanup(p.stop)

    def _poser(self, claude, groq):
        construits = []

        def build(provider=None):
            construits.append(provider or "claude")
            return claude() if (provider or "claude") == "claude" else groq()

        p = mock.patch.object(self.svc.SQLAgentService, "_build_llm",
                              staticmethod(build))
        p.start()
        self.addCleanup(p.stop)
        return construits

    def _question(self):
        import asyncio
        return asyncio.run(self.service.query(
            question="combien de clients ?", user_id=1, company_id=7))

    def test_repli_groq_sur_credits_epuises(self):
        refuse, credit_nul, groq = _llm_factices()
        construits = self._poser(lambda: refuse(messages=iter([]),
                                                erreur=credit_nul()), groq)
        with self.assertLogs(self.svc.logger, level="WARNING") as logs:
            out = self._question()
        self.assertEqual(out["answer"], "Reponse du repli.")
        self.assertTrue(out["repli"])
        self.assertEqual(construits, ["claude", "groq"])
        self.assertTrue(any("credit balance" in m for m in logs.output))

    def test_pas_de_repli_sur_erreur_outil(self):
        refuse, _credit_nul, groq = _llm_factices()
        construits = self._poser(
            lambda: refuse(messages=iter([]),
                           erreur=ValueError("SQL interdit par l'outil")),
            groq)
        out = self._question()
        self.assertEqual(construits, ["claude"])  # jamais rejoue
        self.assertNotIn("Reponse du repli.", out["answer"])
        self.assertFalse(out.get("repli", False))

    def test_sans_fournisseur_de_repli_message_actuel(self):
        refuse, credit_nul, groq = _llm_factices()
        construits = self._poser(lambda: refuse(messages=iter([]),
                                                erreur=credit_nul()), groq)
        with mock.patch.object(self.svc, "SQL_AGENT_FALLBACK_PROVIDER", ""):
            out = self._question()
        self.assertEqual(construits, ["claude"])
        self.assertIn("Je n'ai pas pu traiter", out["answer"])


if __name__ == "__main__":
    unittest.main()
