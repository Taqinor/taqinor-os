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
import contextlib
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._import_optionnel import verifier_import_optionnel  # noqa: E402 — après sys.path/setup() (D-ENF22)

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
    verifier_import_optionnel(exc)

try:
    from fastapi import FastAPI as _FastAPI
    from fastapi.testclient import TestClient as _TestClient
    _HAS_CLIENT = True
except Exception as exc:  # pragma: no cover - starlette/httpx absents
    _FastAPI = None
    _TestClient = None
    _HAS_CLIENT = False
    verifier_import_optionnel(exc)

from app.services import action_tools as _at  # noqa: E402 — après sys.path/setup() (D-ENF22)

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
        # AIC6 — `evenement_id` (nullable) porte l'evenement journalise.
        self.assertIn("evenement_id", _ep.SQLResponse.model_fields)
        self.assertIsNone(_ep.SQLResponse(answer="ok").evenement_id)


@unittest.skipUnless(_OK and _HAS_CLIENT,
                     f"fastapi TestClient indisponible: {_ERR}")
class QueryConfirmLoopTests(unittest.TestCase):
    """Boucle bout-en-bout : /query remonte proposal.confirm_token, ce jeton est
    accepte par /confirm, et une action interne remonte result."""

    def setUp(self):
        from app.core.security import exiger_compte_interne, get_raw_token, verify_token

        app = _FastAPI()
        app.include_router(_ep.router, prefix="/sql-agent")
        app.dependency_overrides[verify_token] = lambda: {
            "user_id": 1, "company_id": 7, "role": "admin",
            "permissions": [], "is_superuser": False,
        }
        app.dependency_overrides[get_raw_token] = lambda: "jwt-xyz"
        app.dependency_overrides[exiger_compte_interne] = lambda: {}  # APFS2
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
        from app.services.cartes import construire_cartes
        from app.services.sql_agent_service import SQLAgentService
        return {
            "answer": "ok", "sql_query": "", "data": None,
            "action_performed": bool(collector),
            "proposal": SQLAgentService._build_proposal_payload(collector),
            "result": SQLAgentService._build_result_payload(collector),
            "cartes": construire_cartes(collector), "moteur": "langchain",
            "evenement_id": 9001,
        }

    def test_query_sert_toutes_les_cartes(self):
        """COP-B1 — deux propositions dans un tour : DEUX cartes (avant, seule
        la derniere etait confirmable) ; `proposal` reste la derniere."""
        async def fake_query(question, user_id=None, company_id=None,
                             action_ctx=None):
            collector = []
            for devis in (45, 46):
                _at.run_catalogue_action(_ctx(), _CAT_PROPOSAL_PDF,
                                         {"id": devis}, collector)
            return self._service_payload(collector)

        with mock.patch.object(_ep.sql_agent_service, "query", fake_query):
            body = self.client.post("/sql-agent/query",
                                    json={"question": "deux PDF"}).json()
        self.assertEqual([c["type"] for c in body["cartes"]],
                         ["proposition", "proposition"])
        jetons = [c["confirm_token"] for c in body["cartes"]]
        self.assertTrue(all(jetons) and jetons[0] != jetons[1])
        self.assertEqual(body["proposal"]["confirm_token"], jetons[1])
        self.assertEqual((body["moteur"], body["evenement_id"]), ("langchain", 9001))

    def test_confirm_sert_la_carte_et_ecrit_l_historique(self):
        """COP-B1 — `/confirm` sert `carte` (fabrique unique) et `suite` null
        sous langchain ; l'action confirmee entre dans l'historique."""
        collector = []
        _at.run_catalogue_action(_ctx(), _CAT_PROPOSAL_PDF, {"id": 9}, collector)
        historique = []
        with mock.patch.object(_at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(_at, "_django_call", lambda *a, **k: {
                    "ok": True, "status": 200, "data": {"id": 9, "statut": "envoye"}}), \
                mock.patch.object(_ep.sql_agent_service, "_ajouter_historique",
                                  lambda uid, msgs: historique.append((uid, msgs))):
            body = self.client.post("/sql-agent/confirm", json={
                "token": collector[0]["confirm_token"]}).json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["carte"]["type"], "resultat")
        self.assertEqual(body["carte"]["action_key"], "ventes.devis.proposal_pdf")
        self.assertEqual(body["carte"]["donnees"], {"id": 9, "statut": "envoye"})
        self.assertIsNone(body["suite"])
        (uid, msgs), = historique
        self.assertEqual((uid, msgs[0]["role"]), (1, "agent"))
        self.assertIn("confirmée", msgs[0]["content"])
        self.assertEqual(msgs[0]["cartes"], [body["carte"]])

    def test_historique_rend_les_cartes_et_relit_l_ancien(self):
        anciens = [{"role": "user", "content": "q"},
                   {"role": "agent", "content": "r"},
                   {"role": "agent", "content": "r2", "cartes": [{"type": "resultat"}]}]
        with mock.patch.object(_ep.sql_agent_service, "_load_history",
                               lambda uid: anciens):
            body = self.client.get("/sql-agent/history").json()
        self.assertEqual(body[0], {"role": "user", "content": "q"})
        self.assertNotIn("cartes", body[1])
        self.assertEqual(body[2]["cartes"], [{"type": "resultat"}])

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

        calls = []

        def fake_call(ctx, path, method="POST", payload=None):
            calls.append(path)
            return {"ok": True, "status": 200, "data": {"pdf": "ok"}}

        with mock.patch.object(_at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(_at, "_django_call", fake_call):
            c = self.client.post("/sql-agent/confirm",
                                 json={"token": prop["confirm_token"]})
        self.assertEqual(c.status_code, 200)
        cbody = c.json()
        self.assertTrue(cbody["ok"])
        self.assertEqual(cbody["action_key"], "ventes.devis.proposal_pdf")
        # CAD177 — AUDV27 a ajoute un DEUXIEME appel a `_django_call` dans
        # `confirm_proposal` : apres l'action reelle, `_log_confirmed_action`
        # journalise la confirmation vers `/api/django/agent/logs/confirmer/`.
        # Un `captured["path"]` unique ecrasait le premier appel par le second
        # (la journalisation), faisant echouer ce test chaque nuit depuis
        # l'ajout d'AUDV27 sans rapport avec MinIO. On verifie desormais les
        # DEUX appels reels plutot que le seul dernier.
        self.assertIn("/api/django/ventes/devis/9/proposal/", calls)
        self.assertIn("/api/django/agent/logs/confirmer/", calls)

    def test_jeton_portail_refuse_403_sans_appel_service(self):
        """APFS2 (C-APFS-001) — la portee est relue par `/auth/me/` : un compte
        portail (ou Django injoignable) recoit 403 sans atteindre le service ;
        un interne passe. Garde du ROUTEUR, rien n'est surcharge ici."""
        from app.core.security import get_raw_token, verify_token
        app = _FastAPI()
        app.include_router(_ep.router, prefix="/sql-agent")
        app.dependency_overrides[verify_token] = lambda: {"user_id": 3, "company_id": 7, "role": "normal"}
        app.dependency_overrides[get_raw_token] = lambda: "jwt-portail"
        client, appels = _TestClient(app), []

        async def fake_query(question, user_id=None, company_id=None, action_ctx=None):
            appels.append(question)
            return {"answer": "ok", "sql_query": "", "data": None}
        for me, attendu in (({"ok": True, "status": 200, "data": {"portee": "portail_client"}}, 403),
                            ({"ok": False, "status": 0, "error": "indisponible"}, 403),
                            ({"ok": True, "status": 200, "data": {"portee": "interne"}}, 200)):
            with mock.patch.object(_at, "_django_call", lambda *a, _me=me, **k: _me), \
                    mock.patch.object(_ep.sql_agent_service, "query", fake_query), \
                    self.assertLogs("app.core.security", "WARNING") if attendu == 403 else contextlib.nullcontext():
                r = client.post("/sql-agent/query", json={"question": "liste des clients"})
            self.assertEqual(r.status_code, attendu, r.text)
            if attendu == 403:
                self.assertEqual(r.json()["detail"], "Accès réservé aux comptes internes.")
                self.assertEqual(appels, [])
        self.assertEqual(appels, ["liste des clients"])

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


@unittest.skipUnless(_OK, f"service sql_agent indisponible: {_ERR}")
class RelevantTableSelectionTests(unittest.TestCase):
    """La selection de tables doit rester BORNEE. Un repli sur TOUTES les tables
    gonfle le prompt au-dela de la limite TPM gratuite de Groq (12k) — c'est la
    cause racine du 413/504 observe en prod. On verifie que le repli mots-cles
    ne renvoie jamais toutes les tables, reste pertinent, et que
    `_get_relevant_tables` retombe sur ce repli borne quand le modele
    d'embeddings est indisponible."""

    def test_keyword_fallback_is_bounded(self):
        from app.services.sql_agent_service import (
            SQLAgentService, _TABLE_DESCRIPTIONS,
        )
        tables = SQLAgentService._keyword_relevant_tables(
            "combien de devis ce mois-ci", k=5)
        self.assertTrue(tables)
        self.assertLessEqual(len(tables), 5)
        self.assertLess(len(tables), len(_TABLE_DESCRIPTIONS))
        for t in tables:
            self.assertIn(t, _TABLE_DESCRIPTIONS)

    def test_keyword_fallback_is_relevant(self):
        from app.services.sql_agent_service import SQLAgentService
        tables = SQLAgentService._keyword_relevant_tables(
            "liste des factures clients", k=5)
        self.assertIn("ventes_facture", tables)

    def test_keyword_fallback_unknown_words_small_core(self):
        from app.services.sql_agent_service import (
            SQLAgentService, _TABLE_DESCRIPTIONS,
        )
        tables = SQLAgentService._keyword_relevant_tables("xyzzy qwerty", k=5)
        self.assertTrue(tables)
        self.assertLess(len(tables), len(_TABLE_DESCRIPTIONS))

    def test_get_relevant_tables_bounded_when_embeddings_fail(self):
        from app.services.sql_agent_service import (
            SQLAgentService, _TABLE_DESCRIPTIONS,
        )
        svc = SQLAgentService()
        with mock.patch.object(
                svc, "_get_embeddings", side_effect=RuntimeError("no model")):
            tables = svc._get_relevant_tables("combien de clients actifs", k=5)
        self.assertTrue(tables)
        self.assertLessEqual(len(tables), 5)
        self.assertLess(len(tables), len(_TABLE_DESCRIPTIONS))


def _llm_simule(reponses):
    """LLM simule (frontiere externe) : rend `reponses` (AIMessage, appels
    d'outils compris) une a une ; journalise les messages recus."""
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    class _Simule(GenericFakeChatModel):
        recus: list = []

        def bind_tools(self, tools, **kwargs):
            self.recus.append(("outils", [t.name for t in tools]))
            return self

        def _generate(self, messages, *a, **k):
            self.recus.append(("messages", list(messages)))
            return super()._generate(messages, *a, **k)

    # disable_streaming : l'executeur appelle `stream` ; un appel d'outil sans
    # texte ne produirait aucun fragment sous le faux modele generique.
    return _Simule(messages=iter(reponses), recus=[], disable_streaming=True)


def _appel_outil(nom, args, ident="appel-1"):
    from langchain_core.messages import AIMessage
    return AIMessage(content="", tool_calls=[{"name": nom, "args": args, "id": ident}])


def _tour(reponses, catalogue=(), django=None, contexte=None, historique=(),
          ctx=None, fournisseur="groq", reglages=None):
    """Un tour du VRAI service (`_query` -> `_run_agent` : executeur, outils,
    gardes) : seuls le LLM, Django et Redis sont simules. Rend (sortie,
    historique ecrit, llm). `reglages` : attributs du service a surcharger."""
    import asyncio
    from sqlalchemy import create_engine, text
    from sqlalchemy.pool import StaticPool
    from app.services import metriques_gouvernees as mg
    from app.services import sql_agent_service as svc

    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE crm_client (id INTEGER, nom TEXT)"))
    service, ecrit, llm = svc.SQLAgentService(), [], _llm_simule(reponses)
    patches = (
        mock.patch.object(_ep._database, "create_sql_agent_engine", lambda: engine),
        mock.patch.multiple(service, _load_history=lambda uid: list(historique),
                            _ajouter_historique=lambda uid, m: ecrit.extend(m),
                            _get_relevant_tables=lambda q: ["crm_client"]),
        mock.patch.object(svc.SQLAgentService, "_build_llm",
                          staticmethod(lambda provider=None: llm)),
        mock.patch.object(mg, "outil_metrique_gouvernee", lambda c, a: None),
        mock.patch.multiple(svc, SQL_AGENT_PROVIDER=fournisseur,
                            SQL_AGENT_FALLBACK_PROVIDER="", **(reglages or {})),
        mock.patch.multiple(_at, fetch_catalogue=lambda c: list(catalogue),
                            _proposal_redis=lambda: _FakeRedis(),
                            ACTION_PROPOSAL_SECRET="sig-secret",
                            _django_call=django or (lambda *a, **k: {
                                "ok": True, "status": 200, "data": {}})),
    )
    with contextlib.ExitStack() as pile:
        for p in patches:
            pile.enter_context(p)
        sortie = asyncio.run(service._query("Prépare ma relance", 1, 7, ctx,
                                            contexte))
    return sortie, ecrit, llm


@unittest.skipUnless(_OK and _HAS_CLIENT, f"service indisponible: {_ERR}")
class TourReelCartesTests(unittest.TestCase):
    """COP-B1 — le vrai `_run_agent` rend toutes les cartes et les ecrit dans
    l'historique avec la reponse."""

    def test_cartes_du_tour_et_historique(self):
        from langchain_core.messages import AIMessage
        sortie, ecrit, _ = _tour(
            [_appel_outil("crm_lead_list", {}),
             _appel_outil("ventes_devis_proposal_pdf", {"id": 45}, "appel-2"),
             AIMessage(content="Voici.")],
            catalogue=_FULL_CATALOGUE, ctx=_ctx(),
            django=lambda *a, **k: {"ok": True, "status": 200,
                                    "data": [{"id": 1489}]})
        self.assertEqual([c["type"] for c in sortie["cartes"]],
                         ["resultat", "proposition"])
        self.assertEqual(sortie["cartes"][0]["donnees"], {"lignes": [{"id": 1489}]})
        self.assertEqual(sortie["moteur"], "langchain")
        self.assertEqual(ecrit[1], {"role": "agent", "content": "Voici.",
                                    "cartes": sortie["cartes"]})

    def test_references_et_entete_remis_au_modele(self):
        """COP-B2 — le DERNIER message d'agent remis au modele porte la ligne
        « Références : … » tiree de ses cartes ; la question porte l'en-tete
        de tour ; l'historique de l'ecran n'est pas modifie."""
        from langchain_core.messages import AIMessage
        touche = {"type": "resultat", "carte": "touche", "donnees": {
            "touche": {"id": 412, "lead": 1489}, "lead": {"lead_id": 1489}}}
        fiche = {"type": "resultat", "carte": "fiche_lead", "donnees": {
            "identite": {"id": 1489}, "devis": [{"id": 45}, {"id": 46}]}}
        historique = [
            {"role": "user", "content": "q1"},
            {"role": "agent", "content": "r1", "cartes": [fiche]},
            {"role": "user", "content": "q2"},
            {"role": "agent", "content": "r2", "cartes": [touche, fiche]}]
        _, _, llm = _tour([AIMessage(content="Noté.")], historique=historique,
                          contexte={"ecran": "/crm/relances", "touche_id": 412})
        messages = next(m for genre, m in llm.recus if genre == "messages")
        textes = [m.content for m in messages]
        self.assertEqual(textes[2], "r1")
        self.assertEqual(textes[4], "r2\n\nRéférences : touche 412 (lead 1489) ; "
                                    "lead 1489 ; devis 45 ; devis 46")
        self.assertTrue(textes[5].startswith("[Contexte donné par l'ERP"))
        self.assertIn("Touche en cours : 412", textes[5])
        self.assertTrue(textes[5].endswith("\n\nPrépare ma relance"))
        self.assertEqual(historique[3]["content"], "r2")

    def test_consignes_du_copilote_dans_le_bloc_en_cache(self):
        """COP-B3 — catalogue avec une action du lot `copilote` : les consignes
        entrent dans le bloc systeme mis en cache (claude) ; sinon le prompt
        d'aujourd'hui, inchange."""
        from langchain_core.messages import AIMessage
        from app.services import prompt_copilote
        from app.services import sql_agent_service as svc

        def systeme(catalogue):
            _, _, llm = _tour([AIMessage(content="ok")], catalogue=catalogue,
                              ctx=_ctx(), fournisseur="claude")
            return next(m for g, m in llm.recus if g == "messages")[0].content

        allume = systeme([dict(_CAT_LEAD_LIST, lot="copilote")])
        self.assertIsInstance(allume, list)
        self.assertEqual(allume[0]["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        self.assertIn(prompt_copilote.CONSIGNES_COPILOTE, allume[0]["text"])
        eteint = systeme([dict(_CAT_LEAD_LIST, lot="herite")])
        self.assertEqual(eteint, svc._contenu_systeme("claude", False)[0])
        self.assertNotIn(prompt_copilote.CONSIGNES_COPILOTE, str(eteint))
        groq, _ = svc._contenu_systeme("groq", True, copilote=True)
        self.assertIn(prompt_copilote.CONSIGNES_COPILOTE, groq)

    def test_outils_appeles_complets_et_limite_en_francais(self):
        """COP-B4 (b, c) — `outils_appeles` porte AUSSI les outils SQL et le
        signalement ; la limite d'iterations rend une phrase francaise."""
        from langchain_core.messages import AIMessage
        sortie, _, _ = _tour(
            [_appel_outil("sql_db_query", {"query": "SELECT nom FROM crm_client"}),
             _appel_outil("report_gap", {"intention": "manque", "resume": "x"}, "a2"),
             _appel_outil("crm_lead_list", {}, "a3"), AIMessage(content="Fini.")],
            catalogue=[_CAT_LEAD_LIST], ctx=_ctx())
        self.assertEqual(sortie["outils_appeles"],
                         ["sql_db_query", "report_gap", "crm.lead.list"])
        boucle = [_appel_outil("sql_db_schema", {"table_names": "crm_client"}, f"s{i}")
                  for i in range(12)]
        sortie, _, _ = _tour(boucle)
        self.assertTrue(sortie["answer"].startswith("Je n'ai pas fini"))
        self.assertNotIn("Agent stopped", sortie["answer"])

    def test_erreur_de_configuration_jamais_montree(self):
        """COP-B4 (a) — une RuntimeError de configuration : message francais
        generique au commercial, detail technique dans l'evenement `bug`."""
        import asyncio
        from app.services import sql_agent_service as svc
        journal, service = [], svc.SQLAgentService()

        def sans_cle(provider=None):
            raise RuntimeError("CLAUDE_API_KEY manquante dans .env")
        with mock.patch.multiple(service, _load_history=lambda uid: [],
                                 _get_relevant_tables=lambda q: ["crm_client"]), \
                mock.patch.object(svc.SQLAgentService, "_build_llm", staticmethod(sans_cle)), \
                mock.patch.object(_ep._database, "create_sql_agent_engine", lambda: None), \
                mock.patch.object(svc, "_apply_tenant_guc", lambda db, cid: None), \
                mock.patch("langchain_community.utilities.SQLDatabase", mock.MagicMock()), \
                mock.patch.object(_at, "journaliser_evenement_assistant",
                                  lambda ctx, corps: journal.append(corps) or 1):
            out = asyncio.run(service.query("Bonjour", 1, 7, None))
        self.assertNotIn("CLAUDE_API_KEY", out["answer"])
        self.assertIn("pas disponible", out["answer"])
        self.assertEqual(journal[0]["intention"], "bug")
        self.assertIn("CLAUDE_API_KEY", journal[0]["erreur"]["message"])

    def test_evenement_porte_tampon_request_id_et_ecritures_de_cache(self):
        """COP-B4 (d, e) — `tokens.cache_write` compte a part ; un evenement
        `bug` / `manque` porte le tampon du navigateur et l'id de requete
        connu du relais ; une `donnee` ne le porte pas."""
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, LLMResult
        from app.services import sql_agent_service as svc
        capture = svc._SQLCapture()
        capture.on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(
            content="", usage_metadata={
                "input_tokens": 1000, "output_tokens": 40, "total_tokens": 1040,
                "input_token_details": {"cache_read": 600, "cache_creation": 300}}))]]))
        self.assertEqual(capture.tokens, {"cache_read": 600, "cache_write": 300,
                                          "input": 100, "output": 40})
        intention, erreur = svc._intention_et_erreur([{
            "type": "erreur", "status": 500, "outil": "crm.lead.note",
            "message": "x", "request_id": "f" * 32}], "donnee")
        self.assertEqual((intention, erreur["request_id"]), ("bug", "f" * 32))
        diag = {"version": "a1", "requetes": [], "erreurs": []}
        envoyes = []
        with mock.patch.object(_at, "journaliser_evenement_assistant",
                               lambda ctx, corps: envoyes.append(corps) or 1):
            for intention in ("manque", "donnee"):
                svc.SQLAgentService._journaliser(
                    "q", {"intention": intention}, None, {"diagnostic": diag})
        self.assertEqual(envoyes[0]["erreur"]["diagnostic"], diag)
        self.assertEqual(envoyes[0]["erreur"]["outil"], "report_gap")
        self.assertIsNone(envoyes[1]["erreur"])
        self.assertEqual(envoyes[1]["tokens"]["cache_write"], 0)

    def test_jeu_d_outils_sql_allege(self):
        """COP-B5 — le modele ne recoit plus `sql_db_query_checker` (appel
        modele cache) ni `sql_db_list_tables` ; une table hors perimetre rend
        l'erreur du schema ET les tables disponibles ; la lecture reste gardee
        (une ecriture est refusee sans etre executee)."""
        from langchain_core.messages import AIMessage
        from app.services import sql_agent_service as svc
        _, _, llm = _tour([AIMessage(content="ok")])
        noms = next(n for g, n in llm.recus if g == "outils")
        self.assertEqual(noms, ["sql_db_query", "sql_db_schema", "report_gap"])
        from sqlalchemy import create_engine, text
        from langchain_community.utilities import SQLDatabase
        engine = create_engine("sqlite://")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE crm_client (id INTEGER, nom TEXT)"))
        lecture, schema = svc.SQLAgentService._outils_sql(
            SQLDatabase(engine, include_tables=["crm_client"]), 7, (False, False, None))
        sortie = schema.invoke({"table_names": "ventes_devis"})
        self.assertIn("Tables disponibles pour cette question : crm_client", sortie)
        self.assertIn("CREATE TABLE crm_client", schema.invoke({"table_names": "crm_client"}))
        self.assertEqual(lecture.invoke({"query": "DELETE FROM crm_client"}),
                         svc._UNSAFE_QUERY_REPLY)

    def test_references_bornees_a_300_caracteres(self):
        from app.services import relais_copilote as relais
        lignes = [{"lead_id": 1000 + i, "touche_id": 5000 + i} for i in range(60)]
        ligne = relais.references_des_cartes([{"donnees": {"lignes": lignes}}])
        self.assertLessEqual(len(ligne), relais.REFERENCES_MAX)
        self.assertTrue(ligne.startswith("Références : touche 5000 (lead 1000) ; "))
        self.assertEqual(relais.references_des_cartes([{"donnees": {}}]), "")


class ContexteEcranAic9Tests(unittest.TestCase):
    """AIC9 — corps de /sql-agent/query : `contexte` {ecran, lead_id} OPTIONNEL,
    injecte dans le message UTILISATEUR et reflete dans l'evenement ; route
    `GET /sql-agent/suggestions` lue du manifeste. COP-B2 : `devis_id`,
    `touche_id`, `diagnostic` borne ; en-tete de tour pose par le serveur,
    prenom et role lus par la SEULE lecture de /auth/me/."""

    ME = {"portee": "interne", "first_name": "Prénom-test",
          "role_nom": "Commercial", "permissions": ["crm_voir"]}

    def setUp(self):
        from app.core.security import exiger_compte_interne, get_raw_token, verify_token
        from app.services import sql_agent_service as svc

        self.svc = svc
        app = _FastAPI()
        app.include_router(_ep.router, prefix="/sql-agent")
        app.dependency_overrides[verify_token] = lambda: {
            "user_id": 1, "company_id": 7, "role": "normal"}
        app.dependency_overrides[get_raw_token] = lambda: "jwt-xyz"
        app.dependency_overrides[exiger_compte_interne] = lambda: {}  # APFS2
        self.client = _TestClient(app)
        for cible, attrs in (
            (_ep._database, {"check_rate_limit": lambda *a, **k: None,
                             "require_sql_agent_enabled": lambda: None}),
            (_at, {"_django_call": self._me}),
        ):
            p = mock.patch.multiple(cible, **attrs)
            p.start()
            self.addCleanup(p.stop)

    def _me(self, ctx, path, method="POST", payload=None):
        self.appels_me = getattr(self, "appels_me", []) + [(path, method)]
        return {"ok": True, "status": 200, "data": dict(self.ME)}

    def _poser(self, corps):
        from app.services import relais_copilote as relais
        recus, journal = {}, []

        async def fake_query(self_, question, user_id, company_id, action_ctx,
                             contexte=None):
            recus["contexte"], recus["ctx"] = contexte, action_ctx
            recus["llm"] = relais.question_du_tour(
                question, contexte, getattr(action_ctx, "identite", None))
            return {"answer": "Deux devis.", "sql_query": "", "data": None}

        with mock.patch.object(self.svc.SQLAgentService, "_query", fake_query), \
                mock.patch.object(_at, "journaliser_evenement_assistant",
                                  lambda ctx, c: journal.append(c) or 9001):
            r = self.client.post("/sql-agent/query", json=corps)
        return r, recus, journal

    def test_contexte_accepte_et_reflete_dans_evenement(self):
        r, recus, journal = self._poser({
            "question": "Combien de devis ?",
            "contexte": {"ecran": "/crm/leads/12", "lead_id": 12}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["evenement_id"], 9001)
        self.assertEqual((journal[0]["ecran"], journal[0]["lead_id"]),
                         ("/crm/leads/12", 12))
        self.assertTrue(recus["llm"].endswith("\n\nCombien de devis ?"))
        self.assertIn("Écran ouvert : /crm/leads/12\nLead ouvert : 12",
                      recus["llm"])
        # Le contexte ne touche jamais le prompt SYSTEME (cache intact).
        systeme, _ = self.svc._contenu_systeme("claude", True)
        self.assertNotIn("/crm/leads/12", str(systeme))

    def test_contexte_optionnel(self):
        r, recus, journal = self._poser({"question": "Combien de devis ?"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(recus["llm"].startswith("[Contexte donné par l'ERP"))
        self.assertNotIn("Écran ouvert", recus["llm"])
        self.assertEqual((journal[0]["ecran"], journal[0]["lead_id"]), ("", None))
        r = self.client.post("/sql-agent/query", json={
            "question": "x", "contexte": {"ecran": "/", "lead_id": "abc"}})
        self.assertEqual(r.status_code, 422)

    def test_entete_identite_du_serveur_une_seule_lecture(self):
        """COP-B2 — prenom et role viennent de /auth/me/ (UNE lecture, qui
        porte aussi les permissions) ; un prenom pose dans le corps est
        ignore ; devis et touche du contexte entrent dans l'en-tete."""
        r, recus, _ = self._poser({"question": "Il ne répond pas.", "contexte": {
            "ecran": "/crm/relances", "devis_id": 45, "touche_id": 412,
            "prenom": "Pirate", "role": "Administrateur"}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.appels_me, [("/api/django/auth/me/", "GET")])
        self.assertEqual(recus["ctx"].permissions, ["crm_voir"])
        self.assertIn("Utilisateur : Prénom-test (rôle Commercial)", recus["llm"])
        self.assertIn("Devis ouvert : 45\nTouche en cours : 412", recus["llm"])
        self.assertNotIn("Pirate", recus["llm"])
        self.assertNotIn("prenom", recus["contexte"])
        r = self.client.post("/sql-agent/query", json={
            "question": "x", "contexte": {"touche_id": "abc"}})
        self.assertEqual(r.status_code, 422)

    def test_entete_date_de_casablanca(self):
        import datetime
        from zoneinfo import ZoneInfo
        from app.services import relais_copilote as relais
        instant = datetime.datetime(2026, 11, 13, 23, 30, tzinfo=datetime.timezone.utc)
        local = instant.astimezone(ZoneInfo("Africa/Casablanca"))
        texte = relais.question_du_tour("Rappelle-le jeudi.", maintenant=instant)
        self.assertIn("%02d h %02d (heure de Casablanca)" % (local.hour, local.minute),
                      texte)
        self.assertNotIn("UTC", texte)

    def test_diagnostic_borne_et_nettoye(self):
        """COP-B2 — tampon du navigateur : 15 requetes et 10 erreurs au plus
        (les plus recentes), chaines tronquees, chaine de requete retiree,
        cles inconnues ecartees."""
        requetes = [{"methode": "POST", "route": f"/api/x/{i}/?tel=0612", "statut": 409,
                     "duree_ms": 12, "request_id": "a" * 32, "corps": {"tel": "0612"}}
                    for i in range(20)]
        erreurs = [{"genre": "script", "message": "m" * 900, "pile": "secret"}
                   for _ in range(12)]
        r, recus, _ = self._poser({"question": "Ça plante", "contexte": {
            "ecran": "/crm/relances", "diagnostic": {
                "version": "a1b2c3d", "requetes": requetes, "erreurs": erreurs,
                "cookies": "sessionid=1"}}})
        self.assertEqual(r.status_code, 200, r.text)
        diag = recus["contexte"]["diagnostic"]
        self.assertEqual(set(diag), {"version", "ecran", "navigateur", "en_ligne",
                                     "requetes", "erreurs"})
        self.assertEqual(len(diag["requetes"]), 15)
        self.assertEqual(diag["requetes"][0]["route"], "/api/x/5/")
        self.assertNotIn("corps", diag["requetes"][0])
        self.assertEqual(len(diag["erreurs"]), 10)
        self.assertEqual(len(diag["erreurs"][0]["message"]), 300)
        self.assertNotIn("pile", diag["erreurs"][0])

    def test_suggestions_servies_depuis_le_manifeste(self):
        import tempfile
        rep = tempfile.mkdtemp()
        with open(os.path.join(rep, "manuel.md"), "w", encoding="utf-8") as f:
            f.write("# Manuel")
        with open(os.path.join(rep, "capacites.yml"), "w", encoding="utf-8") as f:
            f.write("suggestions:\n  /crm/leads:\n    - Q1 ?\n    - Q2 ?\n"
                    "    - Q3 ?\n    - Q4 ?\n  /crm:\n    - Generale ?\n")
        with mock.patch.multiple(self.svc, ASSISTANT_DOCS_DIR=rep, _DOCS_CACHE={}):
            r = self.client.get("/sql-agent/suggestions",
                                params={"ecran": "/crm/leads/12"})
            self.assertEqual(r.json(), ["Q1 ?", "Q2 ?", "Q3 ?"])
            r = self.client.get("/sql-agent/suggestions",
                                params={"ecran": "/crm/clients"})
            self.assertEqual(r.json(), ["Generale ?"])
            r = self.client.get("/sql-agent/suggestions",
                                params={"ecran": "/stock"})
            self.assertEqual(r.json(), [])


if __name__ == "__main__":
    unittest.main()
