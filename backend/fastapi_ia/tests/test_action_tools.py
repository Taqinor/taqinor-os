"""
Tests des outils d'ACTION de l'agent (N86).

Utilisent unittest (stdlib) — aucune cle LLM requise, le reseau Django est
moque. A lancer depuis backend/fastapi_ia :

    python -m unittest discover -s tests

Les dependances runtime du service (httpx, pydantic, langchain_core) doivent
etre installees (image fastapi_ia). Les tests d'outils LangChain se sautent
proprement si langchain_core est absent.
"""
import json
import os
import sys
import unittest
from unittest import mock

# Le service lit la cle Django pour le JWT ; pas necessaire ici mais on evite
# tout effet de bord d'environnement.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")

# Permet d'importer le paquet `app` depuis la racine du service.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import action_tools as at  # noqa: E402 — après sys.path/setup() (D-ENF22)
from app.services.action_tools import ActionContext  # noqa: E402 — après sys.path/setup() (D-ENF22)
from app.services import metriques_gouvernees as mg  # noqa: E402 — après sys.path/setup() (D-ENF22)


def _ctx(role="responsable", permissions=None, token="jwt-xyz",
         is_superuser=False):
    return ActionContext(
        company_id=7, role=role, permissions=permissions or [],
        token=token, is_superuser=is_superuser)


class GatingTests(unittest.TestCase):
    def test_viewer_role_cannot_write(self):
        ctx = _ctx(role="normal", permissions=[])
        self.assertFalse(ctx.can_write(at._TICKET_PERMS))
        self.assertFalse(ctx.can_write(at._BC_PERMS))
        self.assertFalse(ctx.can_write(at._VISITE_PERMS))
        self.assertFalse(ctx.can_act_at_all)

    def test_responsable_can_write(self):
        ctx = _ctx(role="responsable")
        self.assertTrue(ctx.can_write(at._TICKET_PERMS))
        self.assertTrue(ctx.can_act_at_all)

    def test_admin_can_write(self):
        ctx = _ctx(role="admin")
        self.assertTrue(ctx.can_write(at._BC_PERMS))

    def test_superuser_can_write(self):
        ctx = _ctx(role="normal", is_superuser=True)
        self.assertTrue(ctx.can_write(at._VISITE_PERMS))
        self.assertTrue(ctx.can_act_at_all)

    def test_fine_permission_allows_specific_action(self):
        # Un role « normal » muni du droit explicite sav_gerer peut ouvrir un
        # ticket mais pas creer un bon de commande.
        ctx = _ctx(role="normal", permissions=["sav_gerer"])
        self.assertTrue(ctx.can_write(at._TICKET_PERMS))
        self.assertFalse(ctx.can_write(at._BC_PERMS))
        self.assertTrue(ctx.can_act_at_all)


class ActionsAvailableTests(unittest.TestCase):
    def test_no_token_no_actions(self):
        ctx = _ctx(role="admin", token="")
        self.assertFalse(at.actions_available(ctx))

    def test_no_django_url_degrades(self):
        ctx = _ctx(role="admin")
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", ""):
            self.assertFalse(at.actions_available(ctx))

    def test_any_authenticated_with_url_is_available(self):
        # AG2 — la disponibilite ne pre-filtre plus sur les permissions
        # d'ecriture codees en dur : c'est le CATALOGUE (filtre serveur) qui
        # decide quelles actions un appelant voit. Un viewer recoit simplement
        # une liste d'outils vide si son catalogue est vide.
        ctx = _ctx(role="normal", permissions=[])
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"):
            self.assertTrue(at.actions_available(ctx))

    def test_writer_with_url_and_token(self):
        ctx = _ctx(role="responsable")
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"):
            self.assertTrue(at.actions_available(ctx))


class _FakeResp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _patch_post(status_code, payload):
    """Fabrique un faux POST (ctx, path, body) -> resultat, sans reseau."""
    captured = {}

    def fake(ctx, path, body):
        captured["ctx"] = ctx
        captured["path"] = path
        captured["body"] = body
        ok = 200 <= status_code < 300
        if ok:
            return {"ok": True, "status": status_code, "data": payload}
        return {"ok": False, "status": status_code,
                "error": payload.get("detail", "refus")}

    return fake, captured


# ── AG2 — catalogue de test (mime apps/agent/registry.py) ─────────────────────

_CAT_CREATE = {
    "key": "ventes.devis.create",
    "label": "Créer un devis",
    "description": "Crée un devis.",
    "endpoint": "/api/django/ventes/devis/",
    "method": "POST",
    "inputs": {"type": "object", "properties": {
        "client": {"type": "integer"},
        "lignes": {"type": "array"},
    }},
    "required_permission": "ventes_creer",
    "risk": "internal",
    "confirm_summary": None,
}
_CAT_PROPOSAL_PDF = {
    "key": "ventes.devis.proposal_pdf",
    "label": "Générer le PDF",
    "description": "Génère le PDF client.",
    "endpoint": "/api/django/ventes/devis/{id}/proposal/",
    "method": "GET",
    "inputs": {"type": "object", "properties": {"id": {"type": "integer"}},
               "required": ["id"]},
    "required_permission": "ventes_pdf",
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
    "required_permission": "crm_voir",
    "risk": "internal",
    "confirm_summary": None,
}
_CAT_DELETE = {
    "key": "stock.produit.delete",
    "label": "Supprimer un produit",
    "description": "Supprime un produit.",
    "endpoint": "/api/django/stock/produits/{id}/",
    "method": "DELETE",
    "inputs": {"type": "object", "properties": {"id": {"type": "integer"}},
               "required": ["id"]},
    "required_permission": "stock_supprimer",
    "risk": "irreversible",
    "confirm_summary": "Suppression irréversible du produit.",
}
_FULL_CATALOGUE = [_CAT_CREATE, _CAT_PROPOSAL_PDF, _CAT_LEAD_LIST, _CAT_DELETE]

# FG351 — écritures GARDÉES (risk=outward) telles que déclarées dans le
# catalogue Django (apps/agent/registry.py). Elles doivent renvoyer une
# PROPOSITION à confirmer, jamais une exécution immédiate.
_CAT_DEVIS_CREATE_GUARDED = {
    "key": "ventes.devis.create",
    "label": "Créer un devis",
    "description": "Crée un devis (sensible).",
    "endpoint": "/api/django/ventes/devis/",
    "method": "POST",
    "inputs": {"type": "object", "properties": {
        "client": {"type": "integer"},
        "lead": {"type": "integer"},
        "marche": {"type": "string"},
        "lignes": {"type": "array"},
    }},
    "required_permission": "ventes_creer",
    "risk": "outward",
    "confirm_summary": "Créer un devis pour ce client/lead.",
}
_CAT_CLIENT_CREATE = {
    "key": "crm.client.create",
    "label": "Créer un client",
    "description": "Crée une fiche client (sensible).",
    "endpoint": "/api/django/crm/clients/",
    "method": "POST",
    "inputs": {"type": "object", "properties": {
        "nom": {"type": "string"},
        "prenom": {"type": "string"},
        "email": {"type": "string"},
        "telephone": {"type": "string"},
    }, "required": ["nom"]},
    "required_permission": "crm_creer",
    "risk": "outward",
    "confirm_summary": "Créer la fiche client.",
}
_CAT_LEAD_CREATE = {
    "key": "crm.lead.create",
    "label": "Créer un lead",
    "description": "Crée un lead (sensible).",
    "endpoint": "/api/django/crm/leads/",
    "method": "POST",
    "inputs": {"type": "object", "properties": {
        "nom": {"type": "string"},
        "telephone": {"type": "string"},
        "ville": {"type": "string"},
    }, "required": ["nom"]},
    "required_permission": "crm_creer",
    "risk": "outward",
    "confirm_summary": "Créer le lead.",
}
_GUARDED_WRITES = [
    _CAT_DEVIS_CREATE_GUARDED, _CAT_CLIENT_CREATE, _CAT_LEAD_CREATE,
]


def _patch_catalogue(catalogue):
    return mock.patch.object(at, "fetch_catalogue", lambda ctx: list(catalogue))


class BuildToolsTests(unittest.TestCase):
    """AG2 — les outils sont construits DYNAMIQUEMENT depuis le catalogue."""

    def setUp(self):
        try:
            __import__('langchain_core.tools')
        except Exception:
            self.skipTest("langchain_core indisponible dans cet environnement")

    def test_empty_catalogue_gives_no_tools(self):
        ctx = _ctx(role="normal", permissions=[])
        with _patch_catalogue([]):
            self.assertEqual(at.build_action_tools(ctx), [])

    def test_tools_built_from_catalogue(self):
        ctx = _ctx(role="admin")
        with _patch_catalogue(_FULL_CATALOGUE):
            names = {t.name for t in at.build_action_tools(ctx)}
        # cle catalogue -> nom d'outil (points -> underscores).
        self.assertEqual(names, {
            "ventes_devis_create",
            "ventes_devis_proposal_pdf",
            "crm_lead_list",
            "stock_produit_delete",
        })

    def test_outward_tool_description_warns(self):
        ctx = _ctx(role="admin")
        with _patch_catalogue([_CAT_PROPOSAL_PDF]):
            tool = at.build_action_tools(ctx)[0]
        self.assertIn("PROPOSITION", tool.description)

    def test_catalogue_du_tour_deja_lu_n_est_pas_relu(self):
        """Une seule lecture Django par question : le catalogue que le relais
        a déjà lu ce tour (`ctx.catalogue_tour`) sert à construire les outils."""
        ctx = _ctx(role="admin")
        ctx.catalogue_tour = [_CAT_PROPOSAL_PDF]

        def _interdit(ctx):
            raise AssertionError("catalogue relu")
        with mock.patch.object(at, "fetch_catalogue", _interdit):
            names = [t.name for t in at.build_action_tools(ctx)]
        self.assertEqual(names, ["ventes_devis_proposal_pdf"])
        # Sans catalogue du tour (défaut None) : lecture normale.
        self.assertIsNone(_ctx(role="admin").catalogue_tour)
        self.assertEqual(_ctx(role="admin").identite, {})

    def test_tool_args_schema_from_inputs(self):
        ctx = _ctx(role="admin")
        with _patch_catalogue([_CAT_PROPOSAL_PDF]):
            tool = at.build_action_tools(ctx)[0]
        self.assertIn("id", tool.args_schema["properties"])
        self.assertEqual(tool.args_schema["required"], ["id"])


# ── AG2 — validation des entrees contre le JSON-Schema du catalogue ───────────


class ValidateInputsTests(unittest.TestCase):
    def test_unknown_key_rejected(self):
        with self.assertRaises(at.ActionValidationError):
            at.validate_inputs(_CAT_PROPOSAL_PDF["inputs"], {"id": 1, "evil": 2})

    def test_required_missing_rejected(self):
        with self.assertRaises(at.ActionValidationError):
            at.validate_inputs(_CAT_PROPOSAL_PDF["inputs"], {})

    def test_type_mismatch_rejected(self):
        with self.assertRaises(at.ActionValidationError):
            at.validate_inputs(_CAT_PROPOSAL_PDF["inputs"], {"id": [1, 2]})

    def test_numeric_string_coerced(self):
        out = at.validate_inputs(_CAT_PROPOSAL_PDF["inputs"], {"id": "12"})
        self.assertEqual(out["id"], 12)

    def test_only_declared_keys_returned(self):
        out = at.validate_inputs(_CAT_CREATE["inputs"], {"client": 3})
        self.assertEqual(out, {"client": 3})


# ── AG2 — templates de chemin ─────────────────────────────────────────────────


class BuildPathTests(unittest.TestCase):
    def test_path_template_substituted(self):
        path, remaining = at._build_path(
            "/api/django/ventes/devis/{id}/proposal/", {"id": 42})
        self.assertEqual(path, "/api/django/ventes/devis/42/proposal/")
        self.assertEqual(remaining, {})

    def test_missing_path_param_raises(self):
        with self.assertRaises(at.ActionValidationError):
            at._build_path("/x/{id}/", {})

    def test_non_path_inputs_remain_as_body(self):
        path, remaining = at._build_path(
            "/api/django/ventes/devis/", {"client": 3})
        self.assertEqual(path, "/api/django/ventes/devis/")
        self.assertEqual(remaining, {"client": 3})


# ── AG2 — execution internal vs proposition outward/irreversible ──────────────


class _FakeRedis:
    """Redis en memoire minimal (get/set avec ex ignore/delete)."""

    def __init__(self):
        self.store = {}

    def set(self, key, value, ex=None):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def getdel(self, key):  # ACNC42 — lecture + consommation atomiques
        return self.store.pop(key, None)

    def delete(self, key):
        self.store.pop(key, None)


class RunCatalogueActionTests(unittest.TestCase):
    def setUp(self):
        # secret stable pour la signature des propositions.
        self._sec = mock.patch.object(at, "ACTION_PROPOSAL_SECRET", "test-sig-secret")
        self._sec.start()
        self.addCleanup(self._sec.stop)
        self.fake_redis = _FakeRedis()
        self._rds = mock.patch.object(at, "_proposal_redis", lambda: self.fake_redis)
        self._rds.start()
        self.addCleanup(self._rds.stop)

    def test_internal_action_executes_immediately(self):
        ctx = _ctx(role="admin")
        fake, cap = _patch_post(200, {"results": []})
        with mock.patch.object(at, "_django_call",
                               lambda ctx, path, method="POST", payload=None:
                               {"ok": True, "status": 200, "data": {"results": []}}):
            out = at.run_catalogue_action(ctx, _CAT_LEAD_LIST, {})
        parsed = json.loads(out)
        self.assertEqual(parsed["type"], "result")
        self.assertTrue(parsed["ok"])

    def test_internal_action_uses_path_template(self):
        ctx = _ctx(role="admin")
        captured = {}

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            captured["path"] = path
            captured["method"] = method
            return {"ok": True, "status": 200, "data": {}}

        # devis.create est POST simple ; on teste un GET path-template via PDF en
        # le rendant internal pour ce test isole.
        internal_pdf = dict(_CAT_PROPOSAL_PDF, risk="internal")
        with mock.patch.object(at, "_django_call", fake_call):
            at.run_catalogue_action(ctx, internal_pdf, {"id": 7})
        self.assertEqual(captured["path"], "/api/django/ventes/devis/7/proposal/")
        self.assertEqual(captured["method"], "GET")

    def test_outward_action_returns_proposal_not_executed(self):
        ctx = _ctx(role="admin")

        def fake_call(*a, **k):
            raise AssertionError("Une action outward ne doit PAS s'executer.")

        with mock.patch.object(at, "_django_call", fake_call):
            out = at.run_catalogue_action(ctx, _CAT_PROPOSAL_PDF, {"id": 9})
        parsed = json.loads(out)
        self.assertEqual(parsed["type"], "proposal")
        self.assertEqual(parsed["action_key"], "ventes.devis.proposal_pdf")
        self.assertEqual(parsed["inputs"], {"id": 9})
        self.assertTrue(parsed["confirm_token"])
        self.assertIn("human_preview", parsed)

    def test_irreversible_action_returns_proposal(self):
        ctx = _ctx(role="admin")
        with mock.patch.object(at, "_django_call",
                               lambda *a, **k: (_ for _ in ()).throw(
                                   AssertionError("ne doit pas s'executer"))):
            out = at.run_catalogue_action(ctx, _CAT_DELETE, {"id": 3})
        self.assertEqual(json.loads(out)["type"], "proposal")

    def test_offcatalogue_input_rejected_before_execution(self):
        ctx = _ctx(role="admin")
        out = at.run_catalogue_action(ctx, _CAT_CREATE, {"client": 1, "evil": True})
        self.assertIn("refus", out.lower())


class ConfirmProposalTests(unittest.TestCase):
    def setUp(self):
        self._sec = mock.patch.object(at, "ACTION_PROPOSAL_SECRET", "test-sig-secret")
        self._sec.start()
        self.addCleanup(self._sec.stop)
        self.fake_redis = _FakeRedis()
        self._rds = mock.patch.object(at, "_proposal_redis", lambda: self.fake_redis)
        self._rds.start()
        self.addCleanup(self._rds.stop)

    def _stash_pdf(self, ctx):
        """Cree une proposition PDF et renvoie son jeton."""
        with mock.patch.object(at, "_django_call",
                               lambda *a, **k: (_ for _ in ()).throw(
                                   AssertionError("propose only"))):
            out = at.run_catalogue_action(ctx, _CAT_PROPOSAL_PDF, {"id": 5})
        return json.loads(out)["confirm_token"]

    def test_confirm_runs_stashed_proposal(self):
        ctx = _ctx(role="admin")
        token = self._stash_pdf(ctx)
        calls = []

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            calls.append({"path": path, "method": method, "payload": payload})
            return {"ok": True, "status": 200, "data": {"pdf": "ok"}}

        with mock.patch.object(at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        self.assertEqual(calls[0]["path"], "/api/django/ventes/devis/5/proposal/")
        self.assertEqual(calls[0]["method"], "GET")
        # usage unique : le jeton est consomme.
        self.assertIsNone(self.fake_redis.get(at._proposal_key(token)))
        # AUDV27 — la confirmation est journalisee cote Django APRES exécution.
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["path"], "/api/django/agent/logs/confirmer/")
        self.assertEqual(calls[1]["method"], "POST")
        self.assertEqual(calls[1]["payload"]["action_key"],
                         "ventes.devis.proposal_pdf")
        self.assertEqual(calls[1]["payload"]["risk_level"], "outward")

    def test_deux_confirmations_du_meme_jeton_n_executent_qu_une_fois(self):
        """ACNC42 — jeton consomme atomiquement (GETDEL) AVANT l'execution ;
        cle d'idempotence = empreinte du jeton (corps pour le paiement,
        en-tete pour generer-facture), jamais le jeton lui-meme."""
        import hashlib
        props = {"type": "object", "properties": {
            "id": {"type": "integer"}, "montant": {"type": "number"}}, "required": ["id"]}
        paiement = {"key": "ventes.facture.enregistrer_paiement", "label": "Paiement",
                    "endpoint": "/api/django/ventes/factures/{id}/enregistrer-paiement/",
                    "method": "POST", "inputs": props, "risk": "irreversible"}
        facture = {**paiement, "key": "ventes.devis.generer_facture", "risk": "outward",
                   "endpoint": "/api/django/ventes/devis/{id}/generer-facture/"}
        ctx = _ctx(role="admin")
        calls, seconde = [], []

        def fake_call(c, path, method="POST", payload=None, idempotency_key=None):
            calls.append({"path": path, "payload": payload, "cle": idempotency_key})
            if len(calls) == 1:  # confirmation concurrente pendant l'execution
                seconde.append(at.confirm_proposal(ctx, token))
            return {"ok": True, "status": 200, "data": {}}

        with mock.patch.object(at, "_django_call", lambda *a, **k: {"ok": True}):
            token = json.loads(at.run_catalogue_action(
                ctx, paiement, {"id": 30, "montant": 100}))["confirm_token"]
        with mock.patch.object(at, "fetch_catalogue", lambda c: [paiement, facture]), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        # COP-A3 — meme refus, libelle du relais (« deja confirmee »).
        self.assertEqual(seconde[0], {
            "ok": False, "error": "Proposition introuvable, expirée ou déjà confirmée."})
        metier = [c for c in calls if "enregistrer-paiement" in c["path"]]
        self.assertEqual(len(metier), 1)
        empreinte = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.assertEqual(metier[0]["payload"]["idempotency_key"], empreinte)
        self.assertNotIn(token, json.dumps(metier[0]))
        self.assertIsNone(self.fake_redis.get(at._proposal_key(token)))

        calls.clear()
        with mock.patch.object(at, "_django_call", lambda *a, **k: {"ok": True}):
            token = json.loads(at.run_catalogue_action(ctx, facture, {"id": 12}))["confirm_token"]
        with mock.patch.object(at, "fetch_catalogue", lambda c: [paiement, facture]), \
                mock.patch.object(at, "_django_call", fake_call):
            at.confirm_proposal(ctx, token)
        self.assertEqual(calls[0]["cle"], hashlib.sha256(token.encode("utf-8")).hexdigest())
        self.assertNotIn("idempotency_key", calls[0]["payload"] or {})

    def test_confirm_unknown_token(self):
        ctx = _ctx(role="admin")
        res = at.confirm_proposal(ctx, "does-not-exist")
        self.assertFalse(res["ok"])

    def test_confirm_tampered_signature_rejected(self):
        ctx = _ctx(role="admin")
        token = self._stash_pdf(ctx)
        # Altere le record stocke (changement d'inputs) sans re-signer.
        key = at._proposal_key(token)
        rec = json.loads(self.fake_redis.get(key))
        rec["inputs"] = {"id": 999}
        self.fake_redis.set(key, json.dumps(rec))
        with mock.patch.object(at, "fetch_catalogue", lambda c: _FULL_CATALOGUE):
            res = at.confirm_proposal(ctx, token)
        self.assertFalse(res["ok"])

    def test_confirm_wrong_company_rejected(self):
        ctx = _ctx(role="admin")  # company_id=7
        token = self._stash_pdf(ctx)
        other = ActionContext(company_id=99, role="admin", permissions=[],
                              token="jwt-other")
        with mock.patch.object(at, "fetch_catalogue", lambda c: _FULL_CATALOGUE):
            res = at.confirm_proposal(other, token)
        self.assertFalse(res["ok"])

    def test_confirm_action_not_in_catalogue_rejected(self):
        ctx = _ctx(role="admin")
        token = self._stash_pdf(ctx)
        # L'appelant n'a plus l'action dans son catalogue.
        with mock.patch.object(at, "fetch_catalogue", lambda c: [_CAT_LEAD_LIST]):
            res = at.confirm_proposal(ctx, token)
        self.assertFalse(res["ok"])

    def test_confirm_still_succeeds_when_logging_call_fails(self):
        """AUDV27 — la journalisation est best-effort : une panne du 2e appel
        (logs/confirmer/) ne doit JAMAIS faire echouer une action deja
        executee avec succes cote metier."""
        ctx = _ctx(role="admin")
        token = self._stash_pdf(ctx)
        calls = []

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            calls.append(path)
            if path.endswith("/logs/confirmer/"):
                return {"ok": False, "status": 500, "error": "panne"}
            return {"ok": True, "status": 200, "data": {"pdf": "ok"}}

        with mock.patch.object(at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        self.assertEqual(len(calls), 2)

    def test_confirm_revalidates_offcatalogue_inputs(self):
        """Si le catalogue courant a un schema plus strict, des entrees
        devenues hors catalogue sont rejetees a la confirmation."""
        ctx = _ctx(role="admin")
        token = self._stash_pdf(ctx)
        narrowed = dict(_CAT_PROPOSAL_PDF,
                        inputs={"type": "object", "properties": {},
                                "required": []})
        with mock.patch.object(at, "fetch_catalogue", lambda c: [narrowed]):
            res = at.confirm_proposal(ctx, token)
        self.assertFalse(res["ok"])


# ── AG2 (surfacage) — le collecteur capture proposition/resultat ──────────────


class CollectorTests(unittest.TestCase):
    """run_catalogue_action APPEND sa sortie structuree au collecteur fourni —
    c'est ce que /query remonte au frontend (le LLM ne re-emet pas le JSON)."""

    def setUp(self):
        self._sec = mock.patch.object(at, "ACTION_PROPOSAL_SECRET", "test-sig-secret")
        self._sec.start()
        self.addCleanup(self._sec.stop)
        self.fake_redis = _FakeRedis()
        self._rds = mock.patch.object(at, "_proposal_redis", lambda: self.fake_redis)
        self._rds.start()
        self.addCleanup(self._rds.stop)

    def test_outward_appends_proposal_to_collector(self):
        ctx = _ctx(role="admin")
        collector: list = []
        with mock.patch.object(at, "_django_call",
                               lambda *a, **k: (_ for _ in ()).throw(
                                   AssertionError("propose only"))):
            at.run_catalogue_action(ctx, _CAT_PROPOSAL_PDF, {"id": 9}, collector)
        self.assertEqual(len(collector), 1)
        prop = collector[0]
        self.assertEqual(prop["type"], "proposal")
        self.assertEqual(prop["action_key"], "ventes.devis.proposal_pdf")
        self.assertTrue(prop["confirm_token"])

    def test_internal_appends_result_to_collector(self):
        ctx = _ctx(role="admin")
        collector: list = []
        with mock.patch.object(
                at, "_django_call",
                lambda ctx, path, method="POST", payload=None:
                {"ok": True, "status": 200, "data": {"results": []}}):
            at.run_catalogue_action(ctx, _CAT_LEAD_LIST, {}, collector)
        self.assertEqual(len(collector), 1)
        self.assertEqual(collector[0]["type"], "result")

    def test_no_collector_is_safe(self):
        ctx = _ctx(role="admin")
        with mock.patch.object(
                at, "_django_call",
                lambda *a, **k: {"ok": True, "status": 200, "data": {}}):
            out = at.run_catalogue_action(ctx, _CAT_LEAD_LIST, {})
        self.assertEqual(json.loads(out)["type"], "result")

    def test_build_action_tools_threads_collector(self):
        try:
            __import__('langchain_core.tools')
        except Exception:
            self.skipTest("langchain_core indisponible")
        ctx = _ctx(role="admin")
        collector: list = []
        with _patch_catalogue([_CAT_PROPOSAL_PDF]), \
                mock.patch.object(at, "_django_call",
                                  lambda *a, **k: (_ for _ in ()).throw(
                                      AssertionError("propose only"))):
            tools = at.build_action_tools(ctx, collector)
            tools[0].func(id=9)
        self.assertEqual(len(collector), 1)
        self.assertEqual(collector[0]["type"], "proposal")
        # Le jeton appose dans le collecteur EST utilisable par /confirm.
        token = collector[0]["confirm_token"]
        calls = []

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            calls.append(path)
            return {"ok": True, "status": 200, "data": {"pdf": "ok"}}

        with mock.patch.object(at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        self.assertEqual(calls[0], "/api/django/ventes/devis/9/proposal/")


class FetchCatalogueTests(unittest.TestCase):
    def test_no_url_returns_empty(self):
        ctx = _ctx(role="admin")
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", ""):
            self.assertEqual(at.fetch_catalogue(ctx), [])

    def test_relays_get_and_parses_actions(self):
        ctx = _ctx(role="admin")

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            assert method == "GET"
            assert path == at._CATALOGUE_PATH
            return {"ok": True, "status": 200,
                    "data": {"count": 1, "actions": [_CAT_LEAD_LIST]}}

        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"), \
                mock.patch.object(at, "_django_call", fake_call):
            out = at.fetch_catalogue(ctx)
        self.assertEqual([a["key"] for a in out], ["crm.lead.list"])

    def test_failed_fetch_returns_empty(self):
        ctx = _ctx(role="admin")
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"), \
                mock.patch.object(at, "_django_call",
                                  lambda *a, **k: {"ok": False, "error": "down"}):
            self.assertEqual(at.fetch_catalogue(ctx), [])


class GuardedWriteToolsTests(unittest.TestCase):
    """FG351 — « crée un devis / un lead / un client » sont des écritures
    GARDÉES : l'outil renvoie une PROPOSITION signée à confirmer (confirm_token)
    et n'appelle JAMAIS Django à l'exécution directe."""

    def setUp(self):
        self._sec = mock.patch.object(at, "ACTION_PROPOSAL_SECRET", "test-sig-secret")
        self._sec.start()
        self.addCleanup(self._sec.stop)
        self.fake_redis = _FakeRedis()
        self._rds = mock.patch.object(at, "_proposal_redis", lambda: self.fake_redis)
        self._rds.start()
        self.addCleanup(self._rds.stop)

    def _assert_proposal_not_executed(self, action, inputs):
        ctx = _ctx(role="admin")

        def _no_exec(*a, **k):
            raise AssertionError(
                "Une écriture gardée ne doit PAS s'exécuter sans confirmation.")

        collector: list = []
        with mock.patch.object(at, "_django_call", _no_exec):
            out = at.run_catalogue_action(ctx, action, inputs, collector)
        parsed = json.loads(out)
        self.assertEqual(parsed["type"], "proposal")
        self.assertEqual(parsed["action_key"], action["key"])
        self.assertTrue(parsed["confirm_token"])
        self.assertIn("human_preview", parsed)
        # La sortie structurée est aussi remontée au frontend via le collecteur.
        self.assertEqual(len(collector), 1)
        self.assertEqual(collector[0]["type"], "proposal")
        return parsed

    def test_devis_create_returns_proposal(self):
        self._assert_proposal_not_executed(
            _CAT_DEVIS_CREATE_GUARDED, {"client": 3, "marche": "residentiel"})

    def test_client_create_returns_proposal(self):
        parsed = self._assert_proposal_not_executed(
            _CAT_CLIENT_CREATE, {"nom": "Société X", "telephone": "0612345678"})
        self.assertEqual(parsed["inputs"]["nom"], "Société X")

    def test_lead_create_returns_proposal(self):
        self._assert_proposal_not_executed(
            _CAT_LEAD_CREATE, {"nom": "Prospect Y", "ville": "Casablanca"})

    def test_client_create_requires_nom(self):
        ctx = _ctx(role="admin")
        out = at.run_catalogue_action(ctx, _CAT_CLIENT_CREATE, {})
        self.assertIn("refus", out.lower())  # required nom manquant

    def test_offcatalogue_input_rejected_for_lead_create(self):
        ctx = _ctx(role="admin")
        out = at.run_catalogue_action(
            ctx, _CAT_LEAD_CREATE, {"nom": "Z", "evil": True})
        self.assertIn("refus", out.lower())

    def test_confirm_executes_guarded_write_via_internal_rest(self):
        """Après confirmation, la proposition est rejouée vers l'endpoint REST
        interne (relais JWT), pas en écriture DB directe."""
        ctx = _ctx(role="admin")
        prop = self._assert_proposal_not_executed(
            _CAT_CLIENT_CREATE, {"nom": "Confirmé"})
        token = prop["confirm_token"]
        calls = []

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            calls.append({"path": path, "method": method, "payload": payload})
            return {"ok": True, "status": 201, "data": {"id": 42}}

        with mock.patch.object(at, "fetch_catalogue", lambda c: _GUARDED_WRITES), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        self.assertEqual(calls[0]["path"], "/api/django/crm/clients/")
        self.assertEqual(calls[0]["method"], "POST")
        # La société n'est jamais transmise dans le corps : Django l'impose.
        self.assertNotIn("company", calls[0]["payload"] or {})
        # usage unique : le jeton est consommé.
        self.assertIsNone(self.fake_redis.get(at._proposal_key(token)))
        # AUDV27 — la confirmation est journalisee, avec l'id renvoye par
        # Django (`{"id": 42}`) pour que le journal PILOTE (crm.client.create)
        # puisse resoudre content_type/object_id cote Django.
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["path"], "/api/django/agent/logs/confirmer/")
        self.assertEqual(calls[1]["payload"]["action_key"], "crm.client.create")
        self.assertEqual(calls[1]["payload"]["object_id"], 42)

    def test_build_tools_warns_guarded_writes(self):
        try:
            __import__('langchain_core.tools')
        except Exception:
            self.skipTest("langchain_core indisponible")
        ctx = _ctx(role="admin")
        with _patch_catalogue(_GUARDED_WRITES):
            tools = {t.name: t for t in at.build_action_tools(ctx)}
        self.assertEqual(set(tools), {
            "ventes_devis_create", "crm_client_create", "crm_lead_create"})
        for tool in tools.values():
            # outward => la description prévient que l'outil renvoie une
            # PROPOSITION à confirmer (le LLM ne doit pas la croire exécutée).
            self.assertIn("PROPOSITION", tool.description)


# ── AANA18 — preuve HMAC de confirmation (contrat partagé avec Django) ────────
_CONTRAT_LOGS_CONFIRMER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "django_core", "apps", "agent", "contract_samples", "logs_confirmer.json")


class PreuveConfirmationTests(unittest.TestCase):
    """C-AANA-008 / C-AANA-032 — la journalisation transmet une preuve HMAC
    (action + entrées + objet + utilisateur + société) que Django recalcule ;
    `proposal_hash` = cette preuve, jamais le jeton brut. Le format est le
    contrat `apps/agent/contract_samples/logs_confirmer.json`, chargé ici ET
    par `apps/agent/tests_aana_confirmation_prouvee.py`."""

    def setUp(self):
        self._sec = mock.patch.object(at, "ACTION_PROPOSAL_SECRET", "test-sig-secret")
        self._sec.start()
        self.addCleanup(self._sec.stop)
        self.fake_redis = _FakeRedis()
        self._rds = mock.patch.object(at, "_proposal_redis", lambda: self.fake_redis)
        self._rds.start()
        self.addCleanup(self._rds.stop)

    def test_vecteur_du_contrat(self):
        with open(_CONTRAT_LOGS_CONFIRMER, encoding="utf-8") as fh:
            contrat = json.load(fh)
        vecteur = contrat["preuve"]["vecteur_de_test"]
        self.assertEqual(at.message_preuve_confirmation(**vecteur["champs"]),
                         vecteur["message"])
        self.assertEqual(
            at.calculer_preuve_confirmation(secret=vecteur["secret"],
                                            **vecteur["champs"]),
            vecteur["preuve"])
        # Le corps d'exemple porte bien les cles que FastAPI envoie.
        for cle in ("action_key", "risk_level", "inputs", "object_id",
                    "preuve", "proposal_hash"):
            self.assertIn(cle, contrat["exemple_corps"])

    def test_journalisation_porte_la_preuve_de_l_appelant(self):
        import jwt
        jeton = jwt.encode({"user_id": 12, "token_type": "access"},
                           "cle-quelconque", algorithm="HS256")
        ctx = ActionContext(company_id=7, role="admin", permissions=[],
                            token=jeton)
        with mock.patch.object(at, "_django_call",
                               lambda *a, **k: (_ for _ in ()).throw(
                                   AssertionError("propose only"))):
            out = at.run_catalogue_action(ctx, _CAT_CLIENT_CREATE,
                                          {"nom": "Client Confirmé"})
        token = json.loads(out)["confirm_token"]
        calls = []

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            calls.append({"path": path, "payload": payload})
            return {"ok": True, "status": 201, "data": {"id": 42}}

        with mock.patch.dict(os.environ,
                             {"AGENT_HMAC_SECRET": "secret-de-test-contrat"}), \
                mock.patch.object(at, "fetch_catalogue",
                                  lambda c: _GUARDED_WRITES), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        corps = calls[1]["payload"]
        self.assertEqual(calls[1]["path"], "/api/django/agent/logs/confirmer/")
        # Memes champs que le vecteur du contrat => meme preuve.
        with open(_CONTRAT_LOGS_CONFIRMER, encoding="utf-8") as fh:
            vecteur = json.load(fh)["preuve"]["vecteur_de_test"]
        self.assertEqual(corps["preuve"], vecteur["preuve"])
        self.assertEqual(corps["proposal_hash"], corps["preuve"])
        self.assertNotIn(token, json.dumps(corps))

    def test_sans_secret_preuve_vide(self):
        with mock.patch.dict(os.environ, {"AGENT_HMAC_SECRET": ""}):
            self.assertEqual(
                at.calculer_preuve_confirmation(
                    action_key="crm.client.create", company_id=7, user_id=12,
                    inputs={}, object_id=None),
                "")


class JournalEvenementAic6Tests(unittest.TestCase):
    """AIC6 — chaque reponse est journalisee chez Django par le relais (corps
    conforme a assistant_evenement.json, preuve HMAC du relais)."""

    CONTRAT = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "django_core",
        "apps", "agent", "contract_samples", "assistant_evenement.json")

    def _ctx_jwt(self):
        import jwt
        jeton = jwt.encode({"user_id": 301, "company_id": 7}, "x",
                           algorithm="HS256")
        return _ctx(token=jeton)

    def test_journal_evenement_apres_reponse(self):
        from app.services.sql_agent_service import SQLAgentService
        with open(self.CONTRAT, encoding="utf-8") as f:
            contrat = json.load(f)
        appels = []

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            appels.append((path, method, payload))
            return {"ok": True, "status": 201, "data": {"id": 9001}}

        out = {"answer": "Deux devis.", "intention": "donnee",
               "outils_appeles": ["crm.lead.note"], "repli": False,
               "modele": "claude-sonnet-5-5", "manuel_present": True,
               "tokens": {"cache_read": 1800, "input": 420, "output": 96}}
        with mock.patch.dict(os.environ, {"AGENT_HMAC_SECRET": "s3cret"}), \
                mock.patch.object(at, "_django_call", fake_call):
            ev_id = SQLAgentService._journaliser(
                "Combien de devis ?", out, self._ctx_jwt())
        self.assertEqual(ev_id, 9001)
        self.assertEqual(len(appels), 1)
        path, method, corps = appels[0]
        self.assertEqual((path, method), ("/api/django/agent/evenements/", "POST"))
        self.assertEqual(set(corps) - {"preuve"}, set(contrat["exemple_corps"]))
        sans_preuve = {k: v for k, v in corps.items() if k != "preuve"}
        self.assertEqual(corps["preuve"], at.calculer_preuve_confirmation(
            secret="s3cret", action_key="assistant.evenement", company_id=7,
            user_id=301, inputs=sans_preuve, object_id=None))
        self.assertEqual(corps["tokens"], contrat["exemple_corps"]["tokens"])

    def test_echec_de_l_agent_journalise_avec_preuve_signee(self):
        """ERR-ACC-JOURNAL-AGENT-PREUVE-VIDE — l'evenement d'un ECHEC de
        l'agent (intention bug + erreur) part signe comme les autres ; sans
        secret, aucun POST a preuve vide (refuse 400 par Django) : avertissement
        nommant la cause, None, la reponse du commercial reste intacte."""
        # Corps tel que `SQLAgentService._journaliser` le forme sur l'echec
        # (`_query` : intention bug + erreur {status, outil, message}).
        echec = {"intention": "bug", "question": "Montant ?",
                 "resume_reponse": "Je n'ai pas pu traiter votre demande.",
                 "ecran": "", "lead_id": None, "outils_appeles": [],
                 "erreur": {"status": 500, "outil": "assistant",
                            "message": "Error code: 401 - invalid_api_key"},
                 "modele": "openai/gpt-oss-120b", "repli": False,
                 "manuel_present": False,
                 "tokens": {"cache_read": 0, "input": 0, "output": 0}}
        appels = []

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            appels.append(payload)
            return {"ok": True, "status": 201, "data": {"id": 77}}

        with mock.patch.dict(os.environ, {"AGENT_HMAC_SECRET": "s3cret"}), \
                mock.patch.object(at, "_django_call", fake_call):
            ev_id = at.journaliser_evenement_assistant(self._ctx_jwt(),
                                                       dict(echec))
        self.assertEqual(ev_id, 77)
        corps = appels[0]
        self.assertEqual(corps["intention"], "bug")
        sans_preuve = {k: v for k, v in corps.items() if k != "preuve"}
        self.assertEqual(corps["preuve"], at.calculer_preuve_confirmation(
            secret="s3cret", action_key="assistant.evenement", company_id=7,
            user_id=301, inputs=sans_preuve, object_id=None))
        self.assertTrue(corps["preuve"])

        with mock.patch.dict(os.environ, {"AGENT_HMAC_SECRET": ""}), \
                mock.patch.object(at, "_django_call",
                                  lambda *a, **k: self.fail("aucun POST non signe")), \
                self.assertLogs(at.logger, level="WARNING") as journaux:
            self.assertIsNone(at.journaliser_evenement_assistant(
                self._ctx_jwt(), dict(echec)))
        self.assertIn("AGENT_HMAC_SECRET absent", " ".join(journaux.output))

    def test_sans_contexte_aucun_journal(self):
        with mock.patch.object(at, "_django_call",
                               lambda *a, **k: self.fail("aucun appel")):
            self.assertIsNone(at.journaliser_evenement_assistant(None, {}))

    def test_intention_finale_retiree_du_texte(self):
        from app.services import sql_agent_service as svc
        texte, intention = svc._extraire_intention(
            'Cette fonction n\'existe pas.\n<intention>{"intention": "manque"}</intention>')
        self.assertEqual((texte, intention), ("Cette fonction n'existe pas.", "manque"))
        self.assertEqual(svc._extraire_intention("Bonjour")[1], "donnee")
        self.assertEqual(svc._extraire_intention(
            '<intention>{"intention": "pirate"}</intention>')[1], "donnee")

    def test_sortie_en_blocs_de_contenu_anthropic(self):
        """AIC13 (acceptation en direct, 29/10/2026) : sous claude, `output` est
        une liste de blocs ; le texte et la balise finale en sont extraits."""
        from app.services import sql_agent_service as svc
        blocs = [{"type": "text", "text": "Voici le devis."},
                 {"type": "text", "text": "<intention>{\"intention\": \"action\"}</intention>"}]
        self.assertEqual(svc._extraire_intention(blocs), ("Voici le devis.", "action"))
        self.assertEqual(svc._extraire_intention(["a", "b"]), ("ab", "donnee"))
        self.assertEqual(svc._extraire_intention(None), ("", "donnee"))
        self.assertEqual(svc._texte_de_sortie(
            [{"type": "tool_use", "id": "x"}, {"type": "text", "text": "ok"}]), "ok")


class CapteurErreursAic7Tests(unittest.TestCase):
    """AIC7 — un echec inattendu d'une action devient un evenement `bug` sans
    que le modele le decide ; 403/400 restent une reponse normale ;
    `report_gap` signale sans confirmation."""

    def _lancer(self, status):
        collector: list = []
        with mock.patch.object(at, "_django_call", lambda *a, **k: {
                "ok": False, "status": status, "error": "boom"}):
            texte = at.run_catalogue_action(
                _ctx(role="admin"), _CAT_LEAD_LIST, {}, collector)
        return texte, collector

    def _intention(self, collector):
        from app.services import sql_agent_service as svc
        return svc._intention_et_erreur(collector, "donnee")

    def test_action_proposee_ou_executee_vaut_intention_action(self):
        """AIC13 : la balise du modele ne prime pas sur une action reelle."""
        from app.services import sql_agent_service as svc
        proposition = [{"type": "proposal", "action_key": "ventes.devis.accepter"}]
        self.assertEqual(svc._intention_et_erreur(proposition, "hors_champ"),
                         ("action", None))
        resultat = [{"type": "result", "action_key": "crm.lead.note"}]
        self.assertEqual(svc._intention_et_erreur(resultat, "donnee")[0], "action")
        erreur = [{"type": "result", "action_key": "crm.lead.resume"},
                  {"type": "erreur", "intention": "bug", "status": 404,
                   "outil": "crm.lead.resume", "message": "Pas trouve."}]
        self.assertEqual(svc._intention_et_erreur(erreur, "donnee")[0], "bug")
        self.assertEqual(svc._intention_et_erreur([], "hors_champ"),
                         ("hors_champ", None))

    def test_5xx_devient_evenement_bug(self):
        for status in (500, 422, 0):
            with self.subTest(status=status):
                texte, collector = self._lancer(status)
                self.assertIn("a echoue", texte)  # reponse au commercial inchangee
                self.assertEqual(at.intention_pour_statut(status), "bug")
                intention, erreur = self._intention(collector)
                self.assertEqual(intention, "bug")
                self.assertEqual(erreur, {"status": status,
                                          "outil": "crm.lead.list",
                                          "message": "boom"})

    def test_403_et_400_ne_sont_pas_des_bugs(self):
        # COP-A4 — 409 (refus metier) et 404 (objet hors portee) non plus.
        self.assertEqual(at.STATUTS_REPONSE_NORMALE, frozenset({400, 403, 404, 409}))
        for status in sorted(at.STATUTS_REPONSE_NORMALE):
            with self.subTest(status=status):
                _texte, collector = self._lancer(status)
                self.assertEqual(collector, [])
                self.assertEqual(self._intention(collector), ("donnee", None))

    def test_report_gap_sans_confirmation(self):
        collector: list = []
        outil = at.outil_report_gap(collector)
        with mock.patch.object(at, "_django_call",
                               lambda *a, **k: self.fail("aucun appel Django")), \
                mock.patch.object(at, "_stash_proposal",
                                  lambda *a, **k: self.fail("aucune proposition")):
            out = outil.invoke({"intention": "hors_champ",
                                "resume": "Envoyer un e-mail au client",
                                "ecran": "/crm/leads/12"})
        self.assertEqual(out, "signale")
        self.assertEqual(collector, [{
            "type": "signalement", "intention": "hors_champ",
            "resume": "Envoyer un e-mail au client", "ecran": "/crm/leads/12"}])
        self.assertEqual(self._intention(collector), ("hors_champ", None))
        # report_gap n'est jamais une action du catalogue.
        with _patch_catalogue([_CAT_LEAD_LIST]):
            noms = {t.name for t in at.build_action_tools(_ctx(role="admin"))}
        self.assertNotIn("report_gap", noms)


# ---------------------------------------------------------------------------
# NTDATA12 — métriques gouvernées offertes à l'agent NL→SQL (réseau Django moqué)
# ---------------------------------------------------------------------------

CATALOGUE_METRIQUES = {"metriques": [
    {"cle": "dso", "libelle": "DSO", "description": "Délai moyen.",
     "unite": "jours"},
    {"cle": "marge_brute", "libelle": "Marge brute", "description": "",
     "unite": "MAD"},
    {"cle": "Pas Une Cle", "libelle": "x", "description": "", "unite": ""},
]}


class MetriquesGouverneesCatalogueTests(unittest.TestCase):
    def _catalogue(self, reponse, allow_price=False, token="jwt-xyz"):
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"), \
                mock.patch.object(mg, "_django_call",
                                  return_value=reponse) as appel:
            out = mg.catalogue_metriques(_ctx(token=token), allow_price)
        return out, appel

    def test_catalogue_lu_chez_django_avec_le_jeton(self):
        out, appel = self._catalogue({"ok": True, "data": CATALOGUE_METRIQUES})
        self.assertEqual(appel.call_args.args[1], mg.CATALOGUE_PATH)
        self.assertEqual(appel.call_args.kwargs["method"], "GET")
        self.assertEqual([m["cle"] for m in out], ["dso"])

    def test_marge_offerte_seulement_avec_le_droit(self):
        out, _ = self._catalogue({"ok": True, "data": CATALOGUE_METRIQUES},
                                 allow_price=True)
        self.assertEqual([m["cle"] for m in out], ["dso", "marge_brute"])

    def test_django_injoignable_catalogue_vide(self):
        out, _ = self._catalogue({"ok": False, "status": 0, "error": "x"})
        self.assertEqual(out, [])

    def test_sans_jeton_aucun_appel(self):
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"), \
                mock.patch.object(mg, "_django_call") as appel:
            self.assertEqual(mg.catalogue_metriques(_ctx(token="")), [])
        appel.assert_not_called()

    def test_description_cite_les_metriques(self):
        texte = mg.description_outil([
            {"cle": "dso", "libelle": "DSO", "description": "Délai moyen.",
             "unite": "jours"}])
        self.assertIn("PREFERE", texte)
        self.assertIn("- dso : DSO (jours) — Délai moyen.", texte)


class MetriquesGouverneesValeurTests(unittest.TestCase):
    def test_valeur_lue_par_le_resolveur_serveur(self):
        reponse = {"ok": True, "data": {
            "cle": "dso", "libelle": "DSO", "unite": "jours", "valeur": 42.5}}
        with mock.patch.object(mg, "_django_call",
                               return_value=reponse) as appel:
            out = mg.lire_valeur(_ctx(), {"dso"}, "dso")
        self.assertEqual(out["valeur"], 42.5)
        self.assertEqual(appel.call_args.args[1],
                         "/api/django/semantic/metriques/dso/valeur/")
        self.assertEqual(appel.call_args.kwargs["payload"], {"group_by": ""})

    def test_cle_hors_catalogue_refusee_sans_appel(self):
        with mock.patch.object(mg, "_django_call") as appel:
            out = mg.lire_valeur(_ctx(), {"dso"}, "../auth/me")
        self.assertFalse(out["ok"])
        appel.assert_not_called()

    def test_outil_absent_sans_catalogue(self):
        with mock.patch.object(mg, "catalogue_metriques", return_value=[]):
            self.assertIsNone(mg.outil_metrique_gouvernee(_ctx()))

    def test_outil_langchain(self):
        # langchain_core est installé en CI (requirements.txt → langchain) :
        # aucun saut, l'outil LangChain est réellement construit.
        catalogue = [{"cle": "dso", "libelle": "DSO", "description": "",
                      "unite": "jours"}]
        with mock.patch.object(mg, "catalogue_metriques",
                               return_value=catalogue), \
                mock.patch.object(mg, "_django_call", return_value={
                    "ok": True, "data": {"valeur": 3}}):
            outil = mg.outil_metrique_gouvernee(_ctx())
            sortie = json.loads(outil.func(cle="dso"))
        self.assertEqual(outil.name, "metrique_gouvernee")
        self.assertEqual(sortie["valeur"], 3)


class CartesReponseCop1Tests(unittest.TestCase):
    """COP1 — `app.services.cartes` : toutes les sorties du tour, dans l'ordre,
    au format du contrat partagé `assistant_reponse.json` (lu ici, pas recopié)."""

    CONTRAT = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "django_core",
        "apps", "agent", "contract_samples", "assistant_reponse.json")

    def _contrat(self):
        with open(self.CONTRAT, encoding="utf-8") as f:
            return json.load(f)

    def test_deux_propositions_et_un_resultat_gardent_leur_ordre(self):
        from app.services.cartes import construire_cartes
        cartes = construire_cartes([
            {"type": "proposal", "action_key": "a.b", "libelle": "A",
             "human_preview": "A (id=1)", "confirm_token": "t1"},
            {"type": "erreur", "intention": "bug", "status": 500},
            {"type": "result", "action_key": "c.d", "libelle": "C",
             "carte": "touche", "ok": True, "data": {"touche": {"id": 4}}},
            {"type": "proposal", "action_key": "e.f", "libelle": "E",
             "human_preview": "E", "confirm_token": None},
            {"type": "signalement", "intention": "manque"},
        ])
        self.assertEqual([c["type"] for c in cartes],
                         ["proposition", "resultat", "proposition"])
        self.assertEqual([c["action_key"] for c in cartes],
                         ["a.b", "c.d", "e.f"])
        self.assertEqual(cartes[1]["carte"], "touche")
        self.assertEqual(cartes[1]["donnees"], {"touche": {"id": 4}})
        self.assertIsNone(cartes[2]["confirm_token"])

    def test_donnees_est_toujours_un_objet(self):
        from app.services.cartes import construire_cartes
        liste, vide, nue = construire_cartes([
            {"type": "result", "action_key": "x", "data": [{"id": 1}]},
            {"type": "result", "action_key": "y", "data": None},
            {"type": "result", "action_key": "z", "data": 3},
        ])
        self.assertEqual(liste["donnees"], {"lignes": [{"id": 1}]})
        self.assertEqual(vide["donnees"], {})
        self.assertEqual(nue["donnees"], {"valeur": 3})

    def test_cles_des_cartes_egales_au_contrat(self):
        from app.services.cartes import construire_cartes
        contrat = self._contrat()
        proposition, resultat = construire_cartes([
            {"type": "proposal", "action_key": "a", "libelle": "A",
             "human_preview": "A", "confirm_token": "t"},
            {"type": "result", "action_key": "b", "libelle": "B",
             "carte": None, "data": {}},
        ])
        self.assertEqual(set(proposition), set(contrat["carte_proposition"]))
        self.assertEqual(set(resultat), set(contrat["carte_resultat"]))
        for carte in contrat["exemple_deux_propositions"]["cartes"]:
            self.assertEqual(set(carte), set(contrat["carte_proposition"]))
        for carte in contrat["exemple"]["cartes"]:
            self.assertEqual(set(carte), set(contrat["carte_resultat"]))


# ── COP-A1 — sorties du collecteur complètes (cartes) ─────────────────────────

_CONTRATS_AGENT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "django_core",
    "apps", "agent", "contract_samples")


def _contrat_agent(nom):
    with open(os.path.join(_CONTRATS_AGENT, nom), encoding="utf-8") as f:
        return json.load(f)


_CAT_DOCUMENT = {
    "key": "ventes.devis.generer_pdf",
    "label": "Générer le PDF de proposition (devis)",
    "description": "PDF client via /proposal.",
    "endpoint": "/api/django/ventes/devis/{id}/proposal/",
    "method": "GET",
    "inputs": {"type": "object", "properties": {
        "id": {"type": "integer"}, "pdf_mode": {"type": "string"}},
        "required": ["id"]},
    "risk": "internal",
    "carte": "document",
}


class _AvecPropositions(unittest.TestCase):
    """Secret de signature stable + faux Redis des propositions."""

    def setUp(self):
        p = mock.patch.object(at, "ACTION_PROPOSAL_SECRET", "test-sig-secret")
        p.start()
        self.addCleanup(p.stop)
        self.fake_redis = _FakeRedis()
        p = mock.patch.object(at, "_proposal_redis", lambda: self.fake_redis)
        p.start()
        self.addCleanup(p.stop)


class SortiesCollecteurCop1Tests(_AvecPropositions):
    def test_resultat_porte_libelle_et_carte(self):
        from app.services.cartes import construire_cartes
        collector: list = []
        action = dict(_CAT_LEAD_LIST, carte="liste_leads")
        with mock.patch.object(at, "_django_call", lambda *a, **k: {
                "ok": True, "status": 200, "data": {"results": []}}):
            at.run_catalogue_action(_ctx(role="admin"), action, {}, collector)
        self.assertEqual(collector[0]["libelle"], "Lister les leads")
        self.assertEqual(collector[0]["carte"], "liste_leads")
        carte = construire_cartes(collector)[0]
        self.assertEqual(set(carte),
                         set(_contrat_agent("assistant_reponse.json")["carte_resultat"]))
        self.assertEqual((carte["libelle"], carte["carte"]),
                         ("Lister les leads", "liste_leads"))

    def test_proposition_porte_libelle_carte_et_duree_reelle(self):
        from app.services.cartes import construire_cartes
        collector: list = []
        with mock.patch.object(at, "ACTION_PROPOSAL_TTL", 120), \
                mock.patch.object(at, "_django_call", lambda *a, **k: self.fail("propose only")):
            at.run_catalogue_action(_ctx(role="admin"), _CAT_PROPOSAL_PDF, {"id": 9}, collector)
        prop = collector[0]
        self.assertEqual(prop["libelle"], "Générer le PDF")
        self.assertIsNone(prop["carte"])
        self.assertEqual(prop["expire_dans_s"], 120)
        self.assertEqual(construire_cartes(collector)[0]["expire_dans_s"], 120)

    def test_confirmation_rend_libelle_et_carte(self):
        ctx = _ctx(role="admin")
        action = dict(_CAT_DELETE, carte=None)
        with mock.patch.object(at, "_django_call", lambda *a, **k: self.fail("propose only")):
            jeton = json.loads(at.run_catalogue_action(ctx, action, {"id": 3}))["confirm_token"]
        with mock.patch.object(at, "fetch_catalogue", lambda c: [action]), \
                mock.patch.object(at, "_django_call", lambda *a, **k: {
                    "ok": True, "status": 204, "data": {}}):
            res = at.confirm_proposal(ctx, jeton)
        self.assertTrue(res["ok"])
        self.assertEqual(res["libelle"], "Supprimer un produit")
        self.assertIn("carte", res)

    def test_document_rend_le_lien_sans_appeler_django(self):
        contrat = _contrat_agent("assistant_document.json")
        for entrees, attendu in (({"id": 45}, contrat["exemple"]),
                                 ({"id": "45", "pdf_mode": "onepage"}, contrat["exemple_options"])):
            with self.subTest(entrees=entrees):
                collector: list = []
                with mock.patch.object(at, "_django_call",
                                       lambda *a, **k: self.fail("aucun appel Django")):
                    at.run_catalogue_action(_ctx(role="admin"), _CAT_DOCUMENT, entrees, collector)
                self.assertEqual(collector[0]["carte"], "document")
                self.assertEqual(collector[0]["data"], attendu)


# ── COP-A2 — validation fail-closed complète + tolérance de type ──────────────

_SCHEMA_SUIVI = {"type": "object", "properties": {
    "id": {"type": "integer", "description": "Lead."},
    "canal": {"type": "string", "enum": ["whatsapp", "sms", "email"]},
    "quantite": {"type": "string"},
    "montant": {"type": "number"},
    "urgent": {"type": "boolean"},
    "tags": {"type": "array", "items": {"type": "string", "enum": ["chaud", "froid"]}},
    "ids": {"type": "array", "items": {"type": "integer"}},
}, "required": ["id"]}
_CAT_SUIVI = {"key": "crm.lead.brouillon_suivi", "label": "Brouillon de suivi",
              "endpoint": "/api/django/crm/leads/{id}/brouillon-suivi/",
              "method": "GET", "inputs": _SCHEMA_SUIVI, "risk": "internal"}


class ValidationCompleteCop2Tests(unittest.TestCase):
    def _refus(self, entrees):
        with self.assertRaises(at.ActionValidationError) as ctx:
            at.validate_inputs(_SCHEMA_SUIVI, dict({"id": 1}, **entrees))
        return str(ctx.exception)

    def test_enum_refuse_et_liste_les_valeurs_permises(self):
        message = self._refus({"canal": "fax"})
        self.assertIn("whatsapp, sms, email", message)
        self.assertEqual(at.validate_inputs(_SCHEMA_SUIVI, {"id": 1, "canal": "sms"})["canal"], "sms")

    def test_elements_de_tableau_verifies_contre_items(self):
        self.assertIn("chaud, froid", self._refus({"tags": ["chaud", "tiede"]}))
        self.assertIn("ids[1]", self._refus({"ids": [1, "deux"]}))
        out = at.validate_inputs(_SCHEMA_SUIVI, {"id": 1, "ids": ["3", 4], "tags": ["froid"]})
        self.assertEqual((out["ids"], out["tags"]), ([3, 4], ["froid"]))

    def test_coercitions_sures(self):
        out = at.validate_inputs(_SCHEMA_SUIVI, {
            "id": " 12 ", "quantite": 2.5, "montant": "1500.75", "urgent": "Oui"})
        self.assertEqual(out, {"id": 12, "quantite": "2.5", "montant": 1500.75, "urgent": True})
        self.assertIs(at.validate_inputs(_SCHEMA_SUIVI, {"id": 1, "urgent": "non"})["urgent"], False)
        self.assertEqual(at.validate_inputs(_SCHEMA_SUIVI, {"id": 1, "quantite": 3})["quantite"], "3")

    def test_aucune_coercition_hasardeuse(self):
        for entrees in ({"id": "12.5"}, {"id": 12.0}, {"id": "12 lots"},
                        {"urgent": "1"}, {"quantite": True}, {"montant": "1e3"},
                        {"montant": "12,5"}, {"inconnue": 1}):
            with self.subTest(entrees=entrees):
                with self.assertRaises(at.ActionValidationError):
                    at.validate_inputs(_SCHEMA_SUIVI, dict({"id": 1}, **entrees))

    def test_refus_rendu_au_modele_en_texte(self):
        with mock.patch.object(at, "_django_call", lambda *a, **k: self.fail("refuse avant appel")):
            out = at.run_catalogue_action(_ctx(role="admin"), _CAT_SUIVI, {"id": 1, "canal": "fax"})
        self.assertTrue(out.startswith("Action refusee : "))
        self.assertIn("valeurs permises", out)


class SchemaOutilCop2Tests(unittest.TestCase):
    # langchain_core est une dépendance du service : son absence doit faire
    # ÉCHOUER ces tests (jamais les sauter en silence — ENF23).
    def _outil(self):
        with _patch_catalogue([_CAT_SUIVI]):
            return at.build_action_tools(_ctx(role="admin"))[0]

    def test_enum_items_et_requis_visibles_du_modele(self):
        from langchain_core.utils.function_calling import convert_to_openai_tool
        params = convert_to_openai_tool(self._outil())["function"]["parameters"]
        self.assertEqual(params["properties"]["canal"]["enum"], ["whatsapp", "sms", "email"])
        self.assertEqual(params["properties"]["tags"]["items"],
                         {"type": "string", "enum": ["chaud", "froid"]})
        self.assertEqual(params["properties"]["id"]["type"], "integer")
        self.assertEqual(params["required"], ["id"])

    def test_mauvais_type_ne_casse_pas_le_tour(self):
        outil = self._outil()
        with mock.patch.object(at, "_django_call", lambda *a, **k: self.fail("refuse avant appel")):
            for args in ({"id": "abc"}, {}, {"id": 1, "pirate": 2}):
                with self.subTest(args=args):
                    self.assertTrue(outil.invoke(args).startswith("Action refusee : "))


# ── COP-A3 — confirmation à usage unique, liée à l'utilisateur, idempotente ───

class _RedisCourse(_FakeRedis):
    """`getdel` atomique (sous verrou) ; un `get` attend l'autre fil : tout
    code qui LIT puis SUPPRIME laisse passer les deux confirmations."""

    def __init__(self):
        import threading
        super().__init__()
        self.verrou = threading.Lock()
        self.barriere = threading.Barrier(2, timeout=1)

    def getdel(self, key):
        with self.verrou:
            return self.store.pop(key, None)

    def get(self, key):
        import threading
        valeur = self.store.get(key)
        try:
            self.barriere.wait()
        except threading.BrokenBarrierError:
            pass
        return valeur


def _jwt(user_id):
    import jwt
    return jwt.encode({"user_id": user_id, "token_type": "access"},
                      "cle-quelconque", algorithm="HS256")


_CAT_PAIEMENT = {
    "key": "ventes.facture.enregistrer_paiement", "label": "Enregistrer un paiement",
    "endpoint": "/api/django/facturation/factures/{id}/paiements/", "method": "POST",
    "inputs": {"type": "object", "properties": {
        "id": {"type": "integer"}, "montant": {"type": "number"},
        "idempotency_key": {"type": "string"}}, "required": ["id", "montant"]},
    "risk": "irreversible",
}


class ConfirmationUniqueCop3Tests(_AvecPropositions):
    def _proposer(self, ctx, entrees=None):
        with mock.patch.object(at, "_django_call", lambda *a, **k: self.fail("propose only")):
            out = at.run_catalogue_action(ctx, _CAT_PAIEMENT, entrees or {"id": 8, "montant": 100})
        return json.loads(out)["confirm_token"]

    def _confirmer(self, ctx, jeton, reponse=None):
        appels = []

        def fake_call(ctx, path, method="POST", payload=None, idempotency_key=None, **_k):
            appels.append({"path": path, "payload": payload, "cle": idempotency_key})
            return reponse or {"ok": True, "status": 201, "data": {"id": 99}}
        with mock.patch.object(at, "fetch_catalogue", lambda c: [_CAT_PAIEMENT]), \
                mock.patch.object(at, "_django_call", fake_call):
            return at.confirm_proposal(ctx, jeton), appels

    def test_deux_confirmations_concurrentes_une_seule_execution(self):
        import threading
        self.fake_redis = _RedisCourse()
        ctx = _ctx(role="admin", token=_jwt(5))
        jeton = self._proposer(ctx)
        executions, resultats, verrou = [], [], threading.Lock()

        def fake_call(ctx, path, method="POST", payload=None, **_k):
            if "/paiements/" in path:
                with verrou:
                    executions.append(path)
            return {"ok": True, "status": 201, "data": {"id": 99}}
        with mock.patch.object(at, "fetch_catalogue", lambda c: [_CAT_PAIEMENT]), \
                mock.patch.object(at, "_django_call", fake_call):
            fils = [threading.Thread(target=lambda: resultats.append(at.confirm_proposal(ctx, jeton)))
                    for _ in range(2)]
            for f in fils:
                f.start()
            for f in fils:
                f.join(5)
        self.assertEqual(len(executions), 1)
        self.assertEqual(sorted(r["ok"] for r in resultats), [False, True])
        refus = next(r for r in resultats if not r["ok"])
        self.assertEqual(refus["error"], "Proposition introuvable, expirée ou déjà confirmée.")

    def test_autre_utilisateur_de_la_meme_societe_refuse(self):
        jeton = self._proposer(_ctx(role="admin", token=_jwt(5)))
        res, appels = self._confirmer(_ctx(role="admin", token=_jwt(6)), jeton)
        self.assertFalse(res["ok"])
        self.assertIn("autre utilisateur", res["error"])
        self.assertEqual(appels, [])

    def test_cle_d_idempotence_derivee_du_jeton(self):
        import hashlib
        ctx = _ctx(role="admin", token=_jwt(5))
        jeton = self._proposer(ctx)
        res, appels = self._confirmer(ctx, jeton)
        self.assertTrue(res["ok"])
        cle = hashlib.sha256(jeton.encode()).hexdigest()
        # Paiement : la cle voyage dans le CORPS (ACNC42), pas dans l'en-tete.
        self.assertEqual(appels[0]["payload"]["idempotency_key"], cle)
        self.assertIsNone(appels[0]["cle"])
        self.assertNotIn(jeton, json.dumps(appels))
        # Une cle deja fournie par l'entree n'est jamais remplacee.
        jeton = self._proposer(ctx, {"id": 8, "montant": 100, "idempotency_key": "k-1"})
        _res, appels = self._confirmer(ctx, jeton)
        self.assertEqual(appels[0]["payload"]["idempotency_key"], "k-1")

    def test_en_tetes_relayes_sans_remplacer_le_jeton(self):
        envois = []

        class _Client:
            def __init__(self, timeout=None):
                envois.append({"timeout": timeout})

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def request(self, verb, url, **kwargs):
                envois[-1]["headers"] = kwargs["headers"]
                return _FakeResp(200, {})
        court = at.httpx.Timeout(1.0)
        with mock.patch.object(at.httpx, "Client", _Client), \
                mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"):
            at._django_call(_ctx(role="admin"), "/x/", payload={"a": 1}, timeout=court, headers={
                "Idempotency-Key": "k-1", "Authorization": "Bearer pirate"})
        self.assertEqual(envois[0]["headers"]["Idempotency-Key"], "k-1")
        self.assertEqual(envois[0]["headers"]["Authorization"], "Bearer jwt-xyz")
        self.assertIs(envois[0]["timeout"], court)

    def test_echec_apres_reclamation_jeton_consomme(self):
        ctx = _ctx(role="admin", token=_jwt(5))
        for reponse, attendu in (({"ok": False, "status": 409, "error": "Déjà soldée."},
                                  "n'a pas été exécutée ; redemande-la"),
                                 ({"ok": False, "status": 0, "error": "Service indisponible."},
                                  "vérifie si l'action a été faite"),
                                 ({"ok": False, "status": 500, "error": "Erreur interne."},
                                  "vérifie si l'action a été faite")):
            with self.subTest(status=reponse["status"]):
                jeton = self._proposer(ctx)
                res, _ = self._confirmer(ctx, jeton, reponse)
                self.assertFalse(res["ok"])
                self.assertIn(attendu, res["error"])
                res, appels = self._confirmer(ctx, jeton)
                self.assertIn("déjà confirmée", res["error"])
                self.assertEqual(appels, [])


# ── COP-A4 — erreurs dites juste ──────────────────────────────────────────────

class _RespEntetes(_FakeResp):
    def __init__(self, status_code, payload, headers=None):
        super().__init__(status_code, payload)
        self.headers = headers or {}


class ErreursCop4Tests(unittest.TestCase):
    def test_refus_metier_409_et_404_ne_sont_pas_des_bugs(self):
        for status in (409, 404):
            with self.subTest(status=status):
                collector: list = []
                with mock.patch.object(at, "_django_call", lambda *a, **k: {
                        "ok": False, "status": status, "error": "Touche déjà close."}):
                    texte = at.run_catalogue_action(_ctx(role="admin"), _CAT_LEAD_LIST, {}, collector)
                self.assertIsNone(at.intention_pour_statut(status))
                self.assertEqual(collector, [])
                self.assertIn("Touche déjà close.", texte)

    def test_identifiant_de_requete_conserve(self):
        par_entete = at._normalize_error(
            _RespEntetes(500, {"detail": "Erreur serveur."}, {"X-Request-Id": "abc123"}), {"detail": "Erreur serveur."})
        self.assertEqual(par_entete["request_id"], "abc123")
        corps = {"detail": "Erreur.", "error": {"code": "server_error", "message": "Erreur.", "request_id": "r-9"}}
        self.assertEqual(at._normalize_error(_FakeResp(500, corps), corps)["request_id"], "r-9")
        self.assertIsNone(at._normalize_error(_FakeResp(500, {}), {})["request_id"])

    def test_request_id_dans_l_entree_erreur_pas_dans_le_texte_du_modele(self):
        collector: list = []
        with mock.patch.object(at, "_django_call", lambda *a, **k: {
                "ok": False, "status": 500, "error": "Erreur serveur.", "request_id": "rid-77"}):
            texte = at.run_catalogue_action(_ctx(role="admin"), _CAT_LEAD_LIST, {}, collector)
        self.assertEqual(collector[0]["request_id"], "rid-77")
        self.assertNotIn("rid-77", texte)

    def test_message_court_sans_enveloppe_brute(self):
        champs = {"nom": ["Ce champ est obligatoire."], "erreurs": {"rappel_le": "Date passée."},
                  "error": {"code": "validation_error", "message": "Données invalides.", "request_id": "x"}}
        message = at._normalize_error(_FakeResp(400, champs), champs)["error"]
        self.assertEqual(message, "nom: Ce champ est obligatoire. ; erreurs: rappel_le: Date passée.")
        seule = {"error": {"code": "conflict", "message": "Conflit.", "request_id": "x"}}
        self.assertEqual(at._normalize_error(_FakeResp(409, seule), seule)["error"], "Conflit.")
        long = {"detail": "x" * 1000}
        self.assertLessEqual(len(at._normalize_error(_FakeResp(409, long), long)["error"]), 300)


# ── COP-A5 — aperçu qui NOMME l'objet ─────────────────────────────────────────

_CAT_ACCEPTER = {
    "key": "ventes.devis.accepter", "label": "Accepter un devis",
    "confirm_summary": "Accepter ce devis.",
    "endpoint": "/api/django/ventes/devis/{id}/accepter/", "method": "POST",
    "inputs": {"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]},
    "risk": "outward", "objets": {"id": "devis"},
}
_CAT_TOUCHE_REPORTER = {
    "key": "crm.suivi.reporter", "label": "Reporter une touche",
    "endpoint": "/api/django/crm/relance-etapes/{touche_id}/reporter/", "method": "POST",
    "inputs": {"type": "object", "properties": {
        "touche_id": {"type": "integer"}, "lead_id": {"type": "integer"},
        "jours": {"type": "integer"}}, "required": ["touche_id"]},
    "risk": "outward", "objets": {"lead_id": "lead", "touche_id": "touche"},
}


class ApercuNommeCop5Tests(_AvecPropositions):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000")
        p.start()
        self.addCleanup(p.stop)
        self.libelles = _contrat_agent("assistant_libelles.json")

    def _proposer(self, action, entrees, reponse):
        appels = []

        def fake_call(ctx, path, method="POST", payload=None, headers=None, timeout=None):
            appels.append({"path": path, "method": method, "payload": payload, "timeout": timeout})
            return reponse
        collector: list = []
        with mock.patch.object(at, "_django_call", fake_call):
            at.run_catalogue_action(_ctx(role="admin"), action, entrees, collector)
        return collector[0]["human_preview"], appels

    def test_apercu_nomme_le_devis_comme_le_contrat(self):
        apercu, appels = self._proposer(_CAT_ACCEPTER, {"id": 45},
                                        {"ok": True, "status": 200, "data": self.libelles["exemple"]})
        attendu = _contrat_agent("assistant_reponse.json")["exemple_deux_propositions"]["cartes"][0]["apercu"]
        self.assertEqual(apercu, attendu)
        self.assertEqual(len(appels), 1)
        self.assertEqual((appels[0]["path"], appels[0]["method"], appels[0]["payload"]),
                         ("/api/django/agent/libelles/", "GET", {"devis": 45}))
        self.assertLessEqual(appels[0]["timeout"].read, 5)

    def test_plusieurs_objets_et_entrees_restantes(self):
        apercu, appels = self._proposer(
            _CAT_TOUCHE_REPORTER, {"touche_id": 412, "lead_id": 1489, "jours": 3},
            {"ok": True, "status": 200, "data": self.libelles["exemple"]})
        self.assertEqual(appels[0]["payload"], {"lead": 1489, "touche": 412})
        self.assertEqual(apercu, "Reporter une touche — " + self.libelles["exemple"]["lead"]
                         + " ; " + self.libelles["exemple"]["touche"] + " (jours=3)")

    def test_libelle_absent_retombe_sur_la_forme_actuelle(self):
        for reponse in ({"ok": True, "status": 200, "data": self.libelles["exemple_hors_portee"]},
                        {"ok": False, "status": 404, "error": "Introuvable."},
                        {"ok": False, "status": 0, "error": "Service indisponible."}):
            with self.subTest(reponse=reponse):
                apercu, _ = self._proposer(_CAT_ACCEPTER, {"id": 45}, reponse)
                self.assertEqual(apercu, "Accepter ce devis. (id=45)")

    def test_sans_objets_aucun_appel(self):
        apercu, appels = self._proposer(_CAT_DELETE, {"id": 3}, {"ok": True, "data": {}})
        self.assertEqual(appels, [])
        self.assertEqual(apercu, "Suppression irréversible du produit. (id=3)")


# ── COP-A6 — sorties d'outils bornées pour le modèle ──────────────────────────

class SortiesBorneesCop6Tests(unittest.TestCase):
    def _lancer(self, data):
        collector: list = []
        with mock.patch.object(at, "_django_call", lambda *a, **k: {
                "ok": True, "status": 200, "data": data}):
            texte = at.run_catalogue_action(_ctx(role="admin"), _CAT_LEAD_LIST, {}, collector)
        return texte, collector

    @staticmethod
    def _leads(n):
        return [{"id": i, "nom": f"Lead « {i} »", "ville": "Casablanca", "note": "x" * 60}
                for i in range(n)]

    def test_liste_coupee_json_lisible_collecteur_entier(self):
        leads = self._leads(300)
        texte, collector = self._lancer(leads)
        self.assertLessEqual(len(texte), at.LIMITE_SORTIE_MODELE)
        sortie = json.loads(texte)
        self.assertEqual(sortie["suite_coupee"], "… (suite coupée : 300 lignes au total)")
        self.assertTrue(0 < len(sortie["data"]) < 300)
        self.assertEqual(sortie["data"], leads[:len(sortie["data"])])
        self.assertEqual(collector[0]["data"], leads)

    def test_page_drf_garde_ses_autres_cles(self):
        texte, _ = self._lancer({"count": 300, "next": None, "results": self._leads(300)})
        sortie = json.loads(texte)
        self.assertLessEqual(len(texte), at.LIMITE_SORTIE_MODELE)
        self.assertEqual(sortie["data"]["count"], 300)
        self.assertIn("300 lignes au total", sortie["suite_coupee"])

    def test_petite_sortie_inchangee(self):
        texte, collector = self._lancer({"results": self._leads(2)})
        self.assertEqual(json.loads(texte), collector[0])
        self.assertNotIn("suite_coupee", texte)

    def test_corps_sans_liste_extrait_borne(self):
        texte, _ = self._lancer({"texte": 'guillemets "échappés" ' * 2000})
        self.assertLessEqual(len(texte), at.LIMITE_SORTIE_MODELE)
        sortie = json.loads(texte)
        self.assertIn("caractères au total", sortie["suite_coupee"])
        self.assertTrue(sortie["data_extrait"])


if __name__ == "__main__":
    unittest.main()
