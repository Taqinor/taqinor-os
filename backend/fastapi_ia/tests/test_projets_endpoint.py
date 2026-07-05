"""XPRJ29 — Endpoint ``POST /projets/generer-plan``.

Vérifie : sans clé LLM → 503 propre (jamais 500) ; réponse LLM inexploitable
→ 502 ; réponse valide → 200 avec le plan. Le token JWT est mocké (dependency
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
    from app.api.endpoints import projets as _ep
    from app.core.security import verify_token
    from app.services.plan_taches_service import PlanTachesIndisponible
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
    app.include_router(_ep.router, prefix="/projets")
    app.dependency_overrides[verify_token] = lambda: {
        "user_id": 1, "company_id": 7}
    return app


_PAYLOAD = {
    "devis": {
        "id": 1, "montant_materiel": 10000, "montant_main_oeuvre": 2000,
        "nb_lignes_materiel": 3, "nb_lignes_main_oeuvre": 1,
    },
    "type_installation": "residentiel",
}


@unittest.skipUnless(_OK and _HAS_CLIENT, f"endpoint indisponible: {_ERR}")
class GenererPlanEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = _make_app()
        self.client = _TestClient(self.app)

    def test_sans_cle_llm_503(self):
        def _raise(*a, **kw):
            raise PlanTachesIndisponible('GROQ_API_KEY manquante.')
        import app.api.endpoints.projets as mod
        original = mod.generer_plan_taches
        mod.generer_plan_taches = _raise
        try:
            resp = self.client.post("/projets/generer-plan", json=_PAYLOAD)
            self.assertEqual(resp.status_code, 503)
        finally:
            mod.generer_plan_taches = original

    def test_reponse_llm_inexploitable_502(self):
        def _raise(*a, **kw):
            raise ValueError('inexploitable')
        import app.api.endpoints.projets as mod
        original = mod.generer_plan_taches
        mod.generer_plan_taches = _raise
        try:
            resp = self.client.post("/projets/generer-plan", json=_PAYLOAD)
            self.assertEqual(resp.status_code, 502)
        finally:
            mod.generer_plan_taches = original

    def test_plan_valide_200(self):
        def _fake(devis_data, type_installation):
            return {'taches': [
                {'code': '1', 'libelle': 'Étude', 'phase': 'etude',
                 'duree_jours': 2, 'dependances_fs': []},
            ]}
        import app.api.endpoints.projets as mod
        original = mod.generer_plan_taches
        mod.generer_plan_taches = _fake
        try:
            resp = self.client.post("/projets/generer-plan", json=_PAYLOAD)
            self.assertEqual(resp.status_code, 200, resp.text)
            data = resp.json()
            self.assertEqual(len(data['taches']), 1)
            self.assertEqual(data['taches'][0]['code'], '1')
        finally:
            mod.generer_plan_taches = original


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
