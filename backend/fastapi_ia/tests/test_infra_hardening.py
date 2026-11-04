"""ERR85 / ERR86 — Durcissement infra du service FastAPI.

  - ERR85 : create_tables() ne lance du DDL (ALTER/CREATE INDEX) en owner QUE si
    RUN_DB_DDL est explicitement active ; par defaut c'est un no-op.
  - ERR86 : le rate-limit OCR echoue FERME (503) si Redis est indisponible, au
    lieu de laisser passer (sinon le plafond payant Zhipu serait desactive).

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests

Ces modules importent sqlalchemy / fastapi ; si ces deps manquent (env leger),
les tests se sautent proprement.
"""
import ast
import asyncio
import os
import re
import sys
import types
import unittest
import uuid
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MAIN_PY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "main.py")


# ── ERR-JPB-IAAPI-SANS-JOURNAL — une 500 FastAPI laisse une trace ─────────────
class ExceptionNonGereeTests(unittest.TestCase):
    """Le handler est extrait de main.py et joue sans importer l'application
    (ses imports tirent toute la pile agent/OCR, absente d'un environnement
    léger). Le décorateur qui l'enregistre est vérifié sur la source."""

    @classmethod
    def setUpClass(cls):
        with open(MAIN_PY, encoding="utf-8") as fichier:
            cls.source = fichier.read()
        arbre = ast.parse(cls.source)
        fonctions = [n for n in arbre.body
                     if isinstance(n, ast.AsyncFunctionDef)
                     and n.name == "journaliser_exception_non_geree"]
        cls.fonctions = fonctions

    def _handler(self, logger):
        self.assertEqual(len(self.fonctions), 1)
        module = ast.Module(body=self.fonctions, type_ignores=[])

        class Reponse:
            def __init__(self, content, status_code, headers):
                self.content, self.status_code, self.headers = content, status_code, headers

        application = types.SimpleNamespace(exception_handler=lambda _: lambda fonction: fonction)
        espace = {"app": application, "logger": logger, "uuid": uuid, "re": re,
                  "JSONResponse": Reponse, "Request": object}
        exec(compile(module, MAIN_PY, "exec"), espace)  # noqa: S102 - source du depot
        return espace["journaliser_exception_non_geree"]

    def _requete(self, entetes=None):
        return types.SimpleNamespace(
            method="POST", url=types.SimpleNamespace(path="/sql-agent/query"),
            headers=entetes or {})

    def test_enregistre_pour_toute_exception(self):
        self.assertRegex(
            self.source,
            r"@app\.exception_handler\(Exception\)\s+async def journaliser_exception_non_geree")

    def test_journalise_et_repond_500_avec_request_id(self):
        logger = mock.Mock()
        erreur = RuntimeError("boom")
        reponse = asyncio.run(self._handler(logger)(self._requete(), erreur))
        self.assertEqual(reponse.status_code, 500)
        rid = reponse.headers["X-Request-Id"]
        self.assertRegex(rid, r"^[0-9a-f]{32}$")
        self.assertEqual(reponse.content["request_id"], rid)
        logger.error.assert_called_once()
        self.assertIn(rid, logger.error.call_args.args)
        self.assertIs(logger.error.call_args.kwargs["exc_info"], erreur)
        # Jamais le message brut de l'exception côté client.
        self.assertNotIn("boom", str(reponse.content))

    def test_reprend_un_request_id_entrant_valide_seulement(self):
        logger = mock.Mock()
        handler = self._handler(logger)
        rid = "0123456789abcdef0123456789abcdef"
        reponse = asyncio.run(handler(self._requete({"x-request-id": rid}), RuntimeError()))
        self.assertEqual(reponse.headers["X-Request-Id"], rid)
        reponse = asyncio.run(handler(self._requete({"x-request-id": "x\nFAUX"}), RuntimeError()))
        self.assertRegex(reponse.headers["X-Request-Id"], r"^[0-9a-f]{32}$")


# ── ERR85 — gating DDL ────────────────────────────────────────────────────────
from tests._import_optionnel import verifier_import_optionnel  # noqa: E402 — après sys.path/setup() (D-ENF22)

try:
    from app.core import database as _db
    _DB_OK = True
    _DB_ERR = None
except Exception as exc:  # pragma: no cover - sqlalchemy absent
    _db = None
    _DB_OK = False
    _DB_ERR = exc
    verifier_import_optionnel(exc)


@unittest.skipUnless(_DB_OK, f"app.core.database indisponible: {_DB_ERR}")
class DdlGatingTests(unittest.TestCase):
    def test_ddl_disabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RUN_DB_DDL", None)
            self.assertFalse(_db._ddl_enabled())

    def test_ddl_enabled_with_flag(self):
        for val in ("1", "true", "yes", "TRUE"):
            with mock.patch.dict(os.environ, {"RUN_DB_DDL": val}):
                self.assertTrue(_db._ddl_enabled(), val)

    def test_create_tables_noop_when_disabled(self):
        # Sans le flag, create_tables() ne doit toucher NI le metadata NI le DDL.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RUN_DB_DDL", None)
            with mock.patch.object(_db.Base.metadata, "create_all") as m_create, \
                    mock.patch.object(_db.engine, "begin") as m_begin:
                _db.create_tables()
                m_create.assert_not_called()
                m_begin.assert_not_called()


# ── ERR86 — rate-limit OCR fail-closed ────────────────────────────────────────
try:
    from app.api.endpoints import ocr as _ocr
    from fastapi import HTTPException as _HTTPException
    _OCR_OK = True
    _OCR_ERR = None
except Exception as exc:  # pragma: no cover - fastapi absent
    _ocr = None
    _HTTPException = None
    _OCR_OK = False
    _OCR_ERR = exc
    verifier_import_optionnel(exc)


@unittest.skipUnless(_OCR_OK, f"app.api.endpoints.ocr indisponible: {_OCR_ERR}")
class RateLimitFailClosedTests(unittest.TestCase):
    def test_redis_error_denies_with_503(self):
        # _get_redis() leve -> on doit refuser (503), pas laisser passer.
        with mock.patch.object(
            _ocr, "_get_redis", side_effect=RuntimeError("redis down")
        ):
            with self.assertRaises(_HTTPException) as cm:
                _ocr._check_rate_limit("user-1")
            self.assertEqual(cm.exception.status_code, 503)

    def test_over_limit_raises_429(self):
        # Redis OK mais compteur > plafond -> 429.
        fake_redis = mock.Mock()
        pipe = mock.Mock()
        pipe.execute.return_value = [0, 1, _ocr.RATE_LIMIT_MAX + 1, True]
        fake_redis.pipeline.return_value = pipe
        with mock.patch.object(_ocr, "_get_redis", return_value=fake_redis):
            with self.assertRaises(_HTTPException) as cm:
                _ocr._check_rate_limit("user-1")
            self.assertEqual(cm.exception.status_code, 429)

    def test_under_limit_passes(self):
        fake_redis = mock.Mock()
        pipe = mock.Mock()
        pipe.execute.return_value = [0, 1, 1, True]
        fake_redis.pipeline.return_value = pipe
        with mock.patch.object(_ocr, "_get_redis", return_value=fake_redis):
            # Ne doit pas lever.
            _ocr._check_rate_limit("user-1")


# ── AUD401 — confidentialite INTRA-societe de l'agent NL->SQL ────────────────
try:
    from app.services import sql_agent_service as _svc
    _SVC_ERR = None
except Exception as exc:  # pragma: no cover - dependances manquantes
    _svc = None
    _SVC_ERR = exc
    verifier_import_optionnel(exc)


@unittest.skipIf(_svc is None, f"sql_agent_service non importable: {_SVC_ERR}")
class Aud401AccountSecretsTests(unittest.TestCase):
    """`authentication_customuser` est allowlistee et scopee par company_id :
    l'isolation ENTRE societes etait prouvee, mais AUCUNE colonne n'etait bornee
    DANS une societe. Un employe a role minimal pouvait donc extraire les hashes
    PBKDF2 de tous les comptes de sa societe (admins inclus) en une seule
    instruction qui passait tous les gardes. Ces requetes etaient ACCEPTEES
    avant AUD401 ; elles doivent maintenant echouer FERME, avant execution."""

    CID = 7

    def _refused(self, sql):
        with self.assertRaises(_svc.SQLSecurityError):
            _svc._validate_and_secure(sql, self.CID)

    def _accepted(self, sql):
        # Ne doit pas lever : la requete reste securisee normalement.
        self.assertTrue(_svc._validate_and_secure(sql, self.CID))

    # ── Le scenario de l'audit ────────────────────────────────────────────
    def test_hash_de_mot_de_passe_refuse(self):
        self._refused(
            "SELECT username, email, password FROM authentication_customuser")

    def test_etoile_sur_la_table_des_comptes_refusee(self):
        """Un filtre purement lexical serait contourne par `SELECT *`."""
        self._refused("SELECT * FROM authentication_customuser")

    def test_etoile_qualifiee_refusee(self):
        self._refused("SELECT u.* FROM authentication_customuser u")

    def test_etoile_apres_distinct_refusee(self):
        self._refused("SELECT DISTINCT * FROM authentication_customuser")

    # ── Autres secrets de compte ──────────────────────────────────────────
    def test_graine_2fa_refusee(self):
        self._refused(
            "SELECT username, totp_secret FROM authentication_customuser")

    def test_codes_de_secours_2fa_refuses(self):
        self._refused(
            "SELECT totp_recovery_codes FROM authentication_customuser")

    def test_drapeaux_delevation_refuses(self):
        self._refused(
            "SELECT username, is_superuser FROM authentication_customuser")
        self._refused(
            "SELECT username, is_staff FROM authentication_customuser")

    def test_derniere_connexion_refusee(self):
        self._refused(
            "SELECT username, last_login FROM authentication_customuser")

    def test_colonne_masquee_par_un_commentaire_refusee(self):
        self._refused(
            "SELECT username, /* rien a voir */ password "
            "FROM authentication_customuser")

    def test_secret_dans_une_sous_requete_refuse(self):
        self._refused(
            "SELECT username FROM authentication_customuser WHERE password "
            "LIKE 'pbkdf2%'")

    # ── Le garde est INCONDITIONNEL (jamais leve par une permission) ──────
    def test_le_garde_ne_depend_daucune_permission(self):
        """Contrairement au garde prix_achat, aucune permission ne le leve :
        il vit dans `_validate_and_secure`, traverse par TOUT appelant."""
        self.assertTrue(_svc._references_secret_column(
            "SELECT password FROM authentication_customuser"))

    # ── Non-regression : l'usage legitime reste possible ──────────────────
    def test_colonnes_ordinaires_acceptees(self):
        self._accepted(
            "SELECT username, email FROM authentication_customuser")

    def test_comptage_des_comptes_accepte(self):
        self._accepted("SELECT COUNT(*) FROM authentication_customuser")

    def test_politique_de_mot_de_passe_toujours_lisible(self):
        """`password_min_length` n'est PAS un secret : la frontiere de mot doit
        etre stricte (le `_` est un caractere de mot)."""
        self.assertFalse(_svc._references_secret_column(
            "SELECT password_min_length FROM parametres_companyprofile"))
        self.assertFalse(_svc._references_secret_column(
            "SELECT must_change_password FROM authentication_customuser"))

    def test_etoile_sur_une_table_non_sensible_inchangee(self):
        self.assertFalse(
            _svc._references_secret_column("SELECT * FROM crm_client"))


if __name__ == "__main__":
    unittest.main()
