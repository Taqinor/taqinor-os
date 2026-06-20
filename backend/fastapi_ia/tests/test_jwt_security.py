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


if __name__ == "__main__":
    unittest.main()
