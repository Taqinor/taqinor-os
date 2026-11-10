"""AANA8 — `prix_achat_voir` est resolu par `/auth/me/` de Django, plus par le
claim JWT `permissions` (C-AANA-033).

Django n'emet PLUS le claim `permissions` (authentication/serializers.py,
incident nginx du 2026-07-16) : FastAPI lisait `token_payload.get("permissions")`
et obtenait toujours [] — un role porteur de `prix_achat_voir` n'obtenait
jamais la colonne prix d'achat. Les permissions viennent desormais de la source
DB (`UserSerializer.permissions` via `GET /api/django/auth/me/`, relais du JWT
de l'appelant) ; un claim `permissions` forge dans le jeton est IGNORE ; Django
injoignable => aucune permission (fail-closed).

Seuls Django (service HTTP externe a FastAPI), Redis (limiteur) et le LLM sont
simules.

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
    from app.services import action_tools as _at
    _ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    _ep = None
    _ERR = exc
    verifier_import_optionnel(exc)


class _FakeRedis:
    """Limiteur toujours sous le plafond (le debit n'est pas l'objet ici)."""

    class _Pipe:
        def __getattr__(self, name):
            if name == "execute":
                return lambda: [None, 1, 1, True]
            return lambda *a, **k: self

    def pipeline(self):
        return self._Pipe()


@unittest.skipIf(_ep is None, f"endpoint sql_agent non importable: {_ERR}")
class PermissionsAgentTests(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(_db, "get_rate_limit_redis",
                                    lambda: _FakeRedis())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.me_calls = []
        self.contexts = []

        async def fake_query(question, user_id=None, company_id=None,
                             action_ctx=None):
            self.contexts.append(action_ctx)
            return {"answer": "ok", "sql_query": "", "data": None}

        patcher = mock.patch.object(_ep.sql_agent_service, "query", fake_query)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _client(self, payload):
        from app.core.security import exiger_compte_interne, get_raw_token, verify_token

        app = FastAPI()
        app.include_router(_ep.router, prefix="/sql-agent")
        app.dependency_overrides[verify_token] = lambda: payload
        app.dependency_overrides[get_raw_token] = lambda: "jwt-de-l-appelant"
        app.dependency_overrides[exiger_compte_interne] = lambda: {}  # APFS2
        return TestClient(app)

    def _django_me(self, permissions, ok=True):
        def fake_call(ctx, path, method="POST", payload=None):
            self.me_calls.append((path, method, ctx.token))
            if not ok:
                return {"ok": False, "status": 0, "error": "indisponible"}
            return {"ok": True, "status": 200,
                    "data": {"id": 5, "permissions": permissions,
                             "is_superuser": False}}
        patcher = mock.patch.object(_at, "_django_call", fake_call)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _ask(self, payload):
        r = self._client(payload).post(
            "/sql-agent/query",
            json={"question": "quel est le prix d'achat des onduleurs ?"})
        self.assertEqual(r.status_code, 200, r.text)
        return self.contexts[-1]

    _PAYLOAD = {"user_id": 5, "company_id": 7, "role": "normal",
                "is_superuser": False}

    def test_prix_achat_voir_honore(self):
        """Jeton SANS claim `permissions` (forme reelle emise par Django) +
        role porteur de `prix_achat_voir` => permission vue par l'agent."""
        self._django_me(["stock_voir", "prix_achat_voir"])
        ctx = self._ask(dict(self._PAYLOAD))
        self.assertIn("prix_achat_voir", ctx.permissions)
        self.assertIn(("/api/django/auth/me/", "GET", "jwt-de-l-appelant"),
                      self.me_calls)

    def test_sans_permission_reste_refuse(self):
        self._django_me(["stock_voir"])
        ctx = self._ask(dict(self._PAYLOAD))
        self.assertNotIn("prix_achat_voir", ctx.permissions)

    def test_claim_permissions_forge_ignore(self):
        """Le claim n'est plus une source : meme present, il est ignore."""
        self._django_me([])
        ctx = self._ask(dict(self._PAYLOAD, permissions=["prix_achat_voir"]))
        self.assertEqual(ctx.permissions, [])

    def test_django_injoignable_aucune_permission(self):
        self._django_me(["prix_achat_voir"], ok=False)
        ctx = self._ask(dict(self._PAYLOAD))
        self.assertEqual(ctx.permissions, [])

    def test_confirm_resout_aussi_par_auth_me(self):
        self._django_me(["prix_achat_voir"])
        seen = []

        async def fake_confirm(action_ctx, token):
            seen.append(action_ctx)
            return {"ok": False, "error": "x"}

        with mock.patch.object(_ep.sql_agent_service, "confirm_action",
                               fake_confirm):
            self._client(dict(self._PAYLOAD)).post(
                "/sql-agent/confirm", json={"token": "abc"})
        self.assertEqual(seen[0].permissions, ["prix_achat_voir"])


try:
    from app.api.endpoints import ocr as _ocr
    _ERR_OCR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    _ocr, _ERR_OCR = None, exc
    verifier_import_optionnel(exc)


@unittest.skipIf(_ocr is None or _ep is None, f"endpoint ocr non importable: {_ERR_OCR or _ERR}")
class OcrPermissionsTests(unittest.TestCase):
    """APFS46 (C-APFS-040, facette OCR) — l'historique OCR se décide sur les
    codes fins lus par `/auth/me/` (simulé côté HTTP), jamais sur le claim
    `role` (« responsable » pour Admin RH, Technicien responsable…)."""

    CODES = {1: ["users_voir", "rh_voir"],                      # Admin RH
             2: ["installation_voir", "achats_receptionner"],   # Technicien responsable
             3: ["prix_achat_voir", "achats_commander"]}        # Directeur

    def setUp(self):
        from sqlalchemy import BigInteger, create_engine
        from sqlalchemy.ext.compiler import compiles
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from app.core.security import exiger_compte_interne, get_raw_token, verify_token
        from app.models.ocr import OcrDocument
        compiles(BigInteger, "sqlite")(lambda *a, **k: "INTEGER")  # PK auto-incrémentée sous SQLite
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        OcrDocument.__table__.create(engine)
        self.Session = sessionmaker(bind=engine)
        with self.Session() as s:
            s.add_all([OcrDocument(id=10, company_id=7, user_id=1, username="rh", filename="a.pdf"),
                       OcrDocument(id=11, company_id=7, user_id=3, username="dir", filename="b.pdf")])
            s.commit()
        self.me_ok, self.user_id = True, 1
        self.app = FastAPI()
        self.app.include_router(_ocr.router, prefix="/ocr")
        self.app.dependency_overrides[exiger_compte_interne] = lambda: {}
        self.app.dependency_overrides[verify_token] = lambda: {
            "user_id": self.user_id, "company_id": 7, "role": "responsable", "is_superuser": False}
        self.app.dependency_overrides[get_raw_token] = lambda: "jwt"
        self.app.dependency_overrides[_ocr.get_db] = lambda: self.Session()

        def fake_call(ctx, path, method="POST", payload=None):
            if not self.me_ok:
                return {"ok": False, "status": 0, "error": "indisponible"}
            return {"ok": True, "status": 200, "data": {"permissions": self.CODES[self.user_id]}}
        patcher = mock.patch.object(_at, "_django_call", fake_call)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(self.app)

    def _gestes(self, user_id):
        self.user_id = user_id
        ids = sorted(d["id"] for d in self.client.get("/ocr/documents").json())
        save = self.client.post("/ocr/save_document", json={
            "filename": "c.pdf", "type_document": "facture", "texte_brut": "", "donnees_structurees": {},
            "confiance": 0.9}).status_code
        return ids, self.client.delete("/ocr/documents/11").status_code, save

    def test_documents_d_autrui_exigent_prix_achat_voir(self):
        self.assertEqual(self._gestes(1), ([10], 403, 403))       # Admin RH
        self.assertEqual(self._gestes(2), ([], 403, 403))         # Technicien responsable
        self.me_ok = False                                        # /auth/me/ injoignable : fail-closed
        self.assertEqual(self._gestes(1), ([10], 403, 403))
        self.me_ok = True
        ids, suppression, enregistrement = self._gestes(3)        # Directeur
        self.assertEqual((ids, enregistrement), ([10, 11], 200), ids)
        self.assertEqual(suppression, 204)


if __name__ == "__main__":
    unittest.main()
