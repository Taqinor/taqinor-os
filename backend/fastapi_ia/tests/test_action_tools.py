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

from app.services import action_tools as at  # noqa: E402
from app.services.action_tools import ActionContext  # noqa: E402


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
    """Remplace at._django_post pour eviter tout reseau dans les tests."""
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


class OpenTicketTests(unittest.TestCase):
    def test_refused_for_viewer(self):
        ctx = _ctx(role="normal", permissions=[])
        msg = at.open_sav_ticket(ctx, client_id=3, description="panne")
        self.assertIn("refus", msg.lower())

    def test_requires_client(self):
        ctx = _ctx(role="admin")
        msg = at.open_sav_ticket(ctx, client_id=0, description="panne")
        self.assertIn("client", msg.lower())

    def test_requires_description(self):
        ctx = _ctx(role="admin")
        msg = at.open_sav_ticket(ctx, client_id=3, description="   ")
        self.assertIn("description", msg.lower())

    def test_success_posts_to_django(self):
        ctx = _ctx(role="responsable")
        fake, cap = _patch_post(201, {"reference": "SAV-202606-0007"})
        with mock.patch.object(at, "_django_post", fake):
            msg = at.open_sav_ticket(
                ctx, client_id=3, description="onduleur HS",
                installation_id=12, priorite="haute")
        self.assertIn("SAV-202606-0007", msg)
        self.assertEqual(cap["path"], "/api/django/sav/tickets/")
        self.assertEqual(cap["body"]["client"], 3)
        self.assertEqual(cap["body"]["installation"], 12)
        self.assertEqual(cap["body"]["priorite"], "haute")
        # Le contexte (jeton) est bien transmis pour relais Django.
        self.assertEqual(cap["ctx"].token, "jwt-xyz")

    def test_django_refusal_surfaced(self):
        ctx = _ctx(role="responsable")
        fake, _ = _patch_post(403, {"detail": "Acces refuse."})
        with mock.patch.object(at, "_django_post", fake):
            msg = at.open_sav_ticket(ctx, client_id=3, description="x")
        self.assertIn("n'a pas pu", msg.lower())


class DraftBonCommandeTests(unittest.TestCase):
    def test_refused_for_viewer(self):
        ctx = _ctx(role="normal", permissions=["sav_gerer"])  # pas le droit BC
        msg = at.draft_bon_commande_for_chantier(ctx, installation_id=5)
        self.assertIn("refus", msg.lower())

    def test_requires_installation(self):
        ctx = _ctx(role="admin")
        msg = at.draft_bon_commande_for_chantier(ctx, installation_id=0)
        self.assertIn("chantier", msg.lower())

    def test_success(self):
        ctx = _ctx(role="admin")
        fake, cap = _patch_post(201, {"numero": "BCF-1", "nb_lignes": 3})
        with mock.patch.object(at, "_django_post", fake):
            msg = at.draft_bon_commande_for_chantier(
                ctx, installation_id=5, fournisseur_id=2)
        self.assertIn("BCF-1", msg)
        self.assertIn("brouillon", msg.lower())
        self.assertEqual(
            cap["path"],
            "/api/django/installations/chantiers/5/commander-besoin/")
        self.assertEqual(cap["body"]["fournisseur"], 2)


class ScheduleVisitTests(unittest.TestCase):
    def test_refused_for_viewer(self):
        ctx = _ctx(role="normal", permissions=[])
        msg = at.schedule_maintenance_visit(
            ctx, installation_id=5, date_prevue="2026-07-01")
        self.assertIn("refus", msg.lower())

    def test_requires_date(self):
        ctx = _ctx(role="admin")
        msg = at.schedule_maintenance_visit(
            ctx, installation_id=5, date_prevue="")
        self.assertIn("date", msg.lower())

    def test_success_uses_controle_type(self):
        ctx = _ctx(role="responsable")
        fake, cap = _patch_post(201, {"id": 99})
        with mock.patch.object(at, "_django_post", fake):
            msg = at.schedule_maintenance_visit(
                ctx, installation_id=5, date_prevue="2026-07-01",
                technicien_id=8)
        self.assertIn("2026-07-01", msg)
        self.assertEqual(
            cap["path"], "/api/django/installations/interventions/")
        self.assertEqual(cap["body"]["type_intervention"], "controle")
        self.assertEqual(cap["body"]["installation"], 5)
        self.assertEqual(cap["body"]["technicien"], 8)


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


def _patch_catalogue(catalogue):
    return mock.patch.object(at, "fetch_catalogue", lambda ctx: list(catalogue))


class BuildToolsTests(unittest.TestCase):
    """AG2 — les outils sont construits DYNAMIQUEMENT depuis le catalogue."""

    def setUp(self):
        try:
            from langchain_core.tools import StructuredTool  # noqa: F401
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

    def test_tool_args_schema_from_inputs(self):
        ctx = _ctx(role="admin")
        with _patch_catalogue([_CAT_PROPOSAL_PDF]):
            tool = at.build_action_tools(ctx)[0]
        fields = tool.args_schema.model_fields
        self.assertIn("id", fields)


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

        def fake_call(ctx, path, method="POST", payload=None):
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
        captured = {}

        def fake_call(ctx, path, method="POST", payload=None):
            captured["path"] = path
            captured["method"] = method
            return {"ok": True, "status": 200, "data": {"pdf": "ok"}}

        with mock.patch.object(at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        self.assertEqual(captured["path"], "/api/django/ventes/devis/5/proposal/")
        self.assertEqual(captured["method"], "GET")
        # usage unique : le jeton est consomme.
        self.assertIsNone(self.fake_redis.get(at._proposal_key(token)))

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
            from langchain_core.tools import StructuredTool  # noqa: F401
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
        captured = {}

        def fake_call(ctx, path, method="POST", payload=None):
            captured["path"] = path
            return {"ok": True, "status": 200, "data": {"pdf": "ok"}}

        with mock.patch.object(at, "fetch_catalogue", lambda c: _FULL_CATALOGUE), \
                mock.patch.object(at, "_django_call", fake_call):
            res = at.confirm_proposal(ctx, token)
        self.assertTrue(res["ok"])
        self.assertEqual(captured["path"], "/api/django/ventes/devis/9/proposal/")


class FetchCatalogueTests(unittest.TestCase):
    def test_no_url_returns_empty(self):
        ctx = _ctx(role="admin")
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", ""):
            self.assertEqual(at.fetch_catalogue(ctx), [])

    def test_relays_get_and_parses_actions(self):
        ctx = _ctx(role="admin")

        def fake_call(ctx, path, method="POST", payload=None):
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


if __name__ == "__main__":
    unittest.main()
