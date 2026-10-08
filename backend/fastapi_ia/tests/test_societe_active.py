"""AANA7 — FastAPI lit la société ACTIVE du jeton (C-AANA-015).

Django emet le claim `active_company_id` apres une bascule de societe
(`POST /auth/switch-company/`, authentication/active_company.py) et borne
chaque requete Django a cette societe. FastAPI lisait toujours `company_id`
(societe d'attache) : apres bascule vers B, l'agent SQL et l'OCR repondaient
avec les donnees de A (sonde du 05/10 : « societe utilisee=1 (active=2) »).

UN seul helper, `app.core.security.require_company_id`, partage par l'agent SQL
et l'OCR (les deux copies `_require_company_id` sont supprimees).

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
"""
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests._import_optionnel import verifier_import_optionnel  # noqa: E402

try:
    from fastapi import HTTPException

    from app.api.endpoints import ocr as _ocr
    from app.api.endpoints import sql_agent as _sql
    from app.core import security as _security
    _ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    _security = None
    _ERR = exc
    verifier_import_optionnel(exc)


@unittest.skipIf(_security is None, f"app non importable: {_ERR}")
class SocieteActiveTests(unittest.TestCase):

    def test_societe_active_prioritaire(self):
        payload = {"user_id": 1, "company_id": 1, "active_company_id": 2}
        self.assertEqual(_security.require_company_id(payload), 2)
        # Les DEUX appelants passent par le meme helper.
        self.assertEqual(_sql._require_company_id(payload), 2)
        self.assertEqual(_ocr._require_company_id(payload), 2)

    def test_un_seul_helper(self):
        self.assertIs(_sql._require_company_id, _security.require_company_id)
        self.assertIs(_ocr._require_company_id, _security.require_company_id)

    def test_sans_bascule_societe_d_attache(self):
        self.assertEqual(
            _security.require_company_id({"company_id": 1}), 1)
        self.assertEqual(
            _security.require_company_id(
                {"company_id": "3", "active_company_id": None}), 3)

    def test_claim_actif_invalide_ignore(self):
        for bad in (0, "", "abc", -4):
            with self.subTest(active=bad):
                self.assertEqual(
                    _security.require_company_id(
                        {"company_id": 1, "active_company_id": bad}), 1)

    def test_aucune_societe_403(self):
        for payload in ({}, {"company_id": 0}, {"company_id": "abc"},
                        {"company_id": None, "active_company_id": None}):
            with self.subTest(payload=payload):
                with self.assertRaises(HTTPException) as cm:
                    _security.require_company_id(payload)
                self.assertEqual(cm.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
