"""ERR18 — La verification JWT doit EXIGER `exp` (un token sans expiration
n'expirerait jamais) et lier audience/emetteur quand le projet les configure.

Deux niveaux de test :
  1. Si `app.core.security` est importable (CI avec fastapi), on exerce le vrai
     `verify_token` : un token SANS `exp` est rejete (401).
  2. Sinon (env leger sans fastapi), on prouve le contrat de decodage avec PyJWT
     directement : `options={"require": ["exp"]}` rejette un token sans exp.

unittest (stdlib). A lancer depuis backend/fastapi_ia :
    python -m unittest discover -s tests
"""
import datetime
import os
import sys
import unittest

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import jwt as _jwt
    _JWT_OK = True
except Exception:  # pragma: no cover
    _JWT_OK = False

_SECRET = os.environ["DJANGO_SECRET_KEY"]


def _token(payload):
    return _jwt.encode(payload, _SECRET, algorithm="HS256")


class _FakeRequest:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


@unittest.skipUnless(_JWT_OK, "PyJWT indisponible")
class JwtDecodeContractTests(unittest.TestCase):
    """Niveau 2 — contrat de decodage independant de fastapi."""

    def test_token_without_exp_rejected(self):
        tok = _token({"user_id": 1, "company_id": 7, "token_type": "access"})
        with self.assertRaises(_jwt.exceptions.MissingRequiredClaimError):
            _jwt.decode(
                tok, _SECRET, algorithms=["HS256"],
                options={"require": ["exp"], "verify_exp": True},
            )

    def test_token_with_exp_accepted(self):
        exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            hours=1)
        tok = _token({
            "user_id": 1, "company_id": 7, "token_type": "access",
            "exp": exp,
        })
        payload = _jwt.decode(
            tok, _SECRET, algorithms=["HS256"],
            options={"require": ["exp"], "verify_exp": True},
        )
        self.assertEqual(payload["company_id"], 7)

    def test_expired_token_rejected(self):
        exp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            hours=1)
        tok = _token({"token_type": "access", "exp": exp})
        with self.assertRaises(_jwt.exceptions.ExpiredSignatureError):
            _jwt.decode(
                tok, _SECRET, algorithms=["HS256"],
                options={"require": ["exp"], "verify_exp": True},
            )


# Niveau 1 — vrai verify_token (uniquement si fastapi est installe).
try:
    from app.core import security as _sec
    from fastapi import HTTPException as _HTTPException
    _SEC_OK = True
except Exception:  # pragma: no cover - fastapi absent
    _sec = None
    _HTTPException = None
    _SEC_OK = False


@unittest.skipUnless(_SEC_OK and _JWT_OK, "fastapi/security indisponible")
class VerifyTokenTests(unittest.TestCase):
    def test_no_exp_rejected_401(self):
        tok = _token({"user_id": 1, "company_id": 7, "token_type": "access"})
        req = _FakeRequest(cookies={"access_token": tok})
        with self.assertRaises(_HTTPException) as cm:
            _sec.verify_token(req, credentials=None)
        self.assertEqual(cm.exception.status_code, 401)

    def test_valid_token_accepted(self):
        exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            hours=1)
        tok = _token({
            "user_id": 1, "company_id": 7, "token_type": "access", "exp": exp,
        })
        req = _FakeRequest(cookies={"access_token": tok})
        payload = _sec.verify_token(req, credentials=None)
        self.assertEqual(payload["user_id"], 1)

    def test_exp_required_in_claims(self):
        self.assertIn("exp", _sec._REQUIRED_CLAIMS)


@unittest.skipUnless(_SEC_OK and _JWT_OK, "fastapi/security indisponible")
class Aud409SecretKeyStartupGuardTests(unittest.TestCase):
    """AUD409 — `security.py` verifiait les JWT avec une cle VIDE si
    DJANGO_SECRET_KEY manquait : HMAC-SHA256 avec `""` est une cle VALIDE, donc
    n'importe qui forgeait un access token et obtenait l'agent SQL + l'OCR de la
    societe visee. Django porte ce garde depuis toujours (settings/base.py) ;
    FastAPI n'avait AUCUN equivalent. Le module doit desormais echouer FERME au
    chargement."""

    @staticmethod
    def _reimport_without_key():
        """Recharge `app.core.security` sans DJANGO_SECRET_KEY, puis restaure
        l'etat du processus (module d'origine + variable d'environnement)."""
        import importlib
        original = sys.modules.get("app.core.security")
        saved = os.environ.get("DJANGO_SECRET_KEY")
        try:
            os.environ.pop("DJANGO_SECRET_KEY", None)
            sys.modules.pop("app.core.security", None)
            return importlib.import_module("app.core.security")
        finally:
            if saved is not None:
                os.environ["DJANGO_SECRET_KEY"] = saved
            sys.modules.pop("app.core.security", None)
            if original is not None:
                sys.modules["app.core.security"] = original

    def test_chargement_sans_cle_leve_runtimeerror(self):
        with self.assertRaises(RuntimeError):
            self._reimport_without_key()

    def test_cle_vide_casse_le_service_au_lieu_de_l_ouvrir(self):
        """Fait MESURE sur la version epinglee (PyJWT 2.13.0), pour ne rien
        affirmer d'invente : une cle HMAC vide est refusee par la librairie
        elle-meme (`InvalidKeyError`), donc le scenario « jeton force avec une
        chaine vide accepte » n'est PAS reproductible tel quel. Mais
        `InvalidKeyError` n'herite pas d'`InvalidTokenError` : le `except` de
        `verify_token` ne l'attrape pas et le service repondait 500 a CHAQUE
        requete authentifiee. Ce test gele les deux faits qui justifient le
        garde de demarrage — et si une future version de PyJWT tolerait la cle
        vide (vrai contournement d'authentification), il rougirait ici."""
        with self.assertRaises(_jwt.exceptions.InvalidKeyError):
            _jwt.encode({"user_id": 999, "token_type": "access"}, "",
                        algorithm="HS256")
        self.assertFalse(
            issubclass(_jwt.exceptions.InvalidKeyError,
                       _jwt.exceptions.InvalidTokenError),
            "InvalidKeyError attrapee par verify_token : le motif d'echec a "
            "change, relire le garde AUD409.")

    def test_module_charge_normalement_avec_une_cle(self):
        """Non-regression : avec la cle posee, rien ne change."""
        self.assertTrue(_sec._DJANGO_SECRET_KEY)


if __name__ == "__main__":
    unittest.main()
