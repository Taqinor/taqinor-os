"""WIR60 — Endpoint ``POST /kb/redaction`` (assistant IA d'écriture KB, XKB23).

Vérifie : action inconnue -> 400 ; texte/contexte vides -> 400 ; sans clé LLM
-> 503 propre (jamais 500, message reconnu par ``isKeyMissing`` côté
frontend) ; réponse LLM inexploitable -> 502 ; réponse vide -> 502 ; réponse
valide -> 200 avec le texte généré. Le token JWT est mocké (dependency
override) — ce test ne vérifie PAS l'authentification (déjà couverte par
``test_jwt_security.py``), seulement le contrat de l'endpoint.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
"""
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.api.endpoints import kb as _ep
    from app.core.security import verify_token
    _OK = True
    _ERR = None
except Exception as exc:  # pragma: no cover - fastapi absent
    _ep = None
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


def _make_app():
    app = _FastAPI()
    app.include_router(_ep.router, prefix="/kb")
    app.dependency_overrides[verify_token] = lambda: {
        "user_id": 1, "company_id": 7}
    return app


@unittest.skipUnless(_OK and _HAS_CLIENT, f"endpoint indisponible: {_ERR}")
class KbRedactionEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        self.client = _TestClient(self.app)

    def _patch_run(self, fn):
        import app.api.endpoints.kb as mod
        original = mod._run_redaction
        mod._run_redaction = fn
        return mod, original

    def test_action_inconnue_400(self):
        resp = self.client.post(
            "/kb/redaction", json={"action": "sabordage", "texte": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_texte_et_contexte_vides_400(self):
        resp = self.client.post(
            "/kb/redaction", json={"action": "reformuler", "texte": "  "})
        self.assertEqual(resp.status_code, 400)

    def test_sans_cle_llm_503(self):
        def _raise(*a, **kw):
            raise RuntimeError("GROQ_API_KEY manquante dans .env")
        mod, original = self._patch_run(_raise)
        try:
            resp = self.client.post(
                "/kb/redaction", json={"action": "corriger", "texte": "salu"})
            self.assertEqual(resp.status_code, 503)
            self.assertIn("GROQ_API_KEY", resp.json()["detail"])
        finally:
            mod._run_redaction = original

    def test_reponse_llm_inexploitable_502(self):
        def _raise(*a, **kw):
            raise ValueError("inexploitable")
        mod, original = self._patch_run(_raise)
        try:
            resp = self.client.post(
                "/kb/redaction", json={"action": "resumer", "texte": "un long texte"})
            self.assertEqual(resp.status_code, 502)
        finally:
            mod._run_redaction = original

    def test_reponse_vide_502(self):
        mod, original = self._patch_run(lambda *a, **kw: "")
        try:
            resp = self.client.post(
                "/kb/redaction", json={"action": "generer", "texte": "titre : panneaux solaires"})
            self.assertEqual(resp.status_code, 502)
        finally:
            mod._run_redaction = original

    def test_action_valide_200(self):
        def _fake(action, texte, contexte):
            self.assertEqual(action, "traduire_fr_ar")
            self.assertEqual(texte, "bonjour")
            return "مرحبا"
        mod, original = self._patch_run(_fake)
        try:
            resp = self.client.post(
                "/kb/redaction",
                json={"action": "traduire_fr_ar", "texte": "bonjour"})
            self.assertEqual(resp.status_code, 200, resp.text)
            self.assertEqual(resp.json()["texte"], "مرحبا")
        finally:
            mod._run_redaction = original

    def test_generer_avec_contexte_seul_ok(self):
        # WIR60 — `texte` peut être vide côté générer/résumer (page vierge) :
        # seul `contexte` compte alors comme entrée exploitable.
        def _fake(action, texte, contexte):
            self.assertEqual(contexte, "panneaux solaires résidentiels")
            return "Un article généré."
        mod, original = self._patch_run(_fake)
        try:
            resp = self.client.post(
                "/kb/redaction",
                json={"action": "generer", "texte": "",
                      "contexte": "panneaux solaires résidentiels"})
            self.assertEqual(resp.status_code, 200, resp.text)
        finally:
            mod._run_redaction = original


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
