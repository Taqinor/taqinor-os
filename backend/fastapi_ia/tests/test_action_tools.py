"""
Tests des outils d'ACTION de l'agent (N86).

Utilisent unittest (stdlib) — aucune cle LLM requise, le reseau Django est
moque. A lancer depuis backend/fastapi_ia :

    python -m unittest discover -s tests

Les dependances runtime du service (httpx, pydantic, langchain_core) doivent
etre installees (image fastapi_ia). Les tests d'outils LangChain se sautent
proprement si langchain_core est absent.
"""
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

    def test_viewer_no_actions(self):
        ctx = _ctx(role="normal", permissions=[])
        with mock.patch.object(at, "DJANGO_INTERNAL_URL", "http://dj:8000"):
            self.assertFalse(at.actions_available(ctx))

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


class BuildToolsTests(unittest.TestCase):
    def setUp(self):
        try:
            from langchain_core.tools import StructuredTool  # noqa: F401
        except Exception:
            self.skipTest("langchain_core indisponible dans cet environnement")

    def test_viewer_gets_no_tools(self):
        ctx = _ctx(role="normal", permissions=[])
        self.assertEqual(at.build_action_tools(ctx), [])

    def test_writer_gets_three_tools(self):
        ctx = _ctx(role="admin")
        names = {t.name for t in at.build_action_tools(ctx)}
        self.assertEqual(names, {
            "ouvrir_ticket_sav",
            "brouillon_bon_commande_chantier",
            "planifier_visite_maintenance",
        })

    def test_fine_perm_gets_only_ticket_tool(self):
        ctx = _ctx(role="normal", permissions=["sav_gerer"])
        names = {t.name for t in at.build_action_tools(ctx)}
        self.assertEqual(names, {"ouvrir_ticket_sav"})


if __name__ == "__main__":
    unittest.main()
