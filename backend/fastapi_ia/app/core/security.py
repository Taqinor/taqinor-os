"""
Verification JWT pour FastAPI.
Lit le token depuis le cookie httpOnly 'access_token' en priorite,
puis depuis l'en-tete Authorization: Bearer (fallback).
"""
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError

_DJANGO_SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
_ALGORITHM = "HS256"

# ERR18 — Liaison optionnelle audience / emetteur : si le projet definit ces
# claims (JWT_AUDIENCE / JWT_ISSUER), ils sont verifies ; sinon non-cassant.
_JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "") or None
_JWT_ISSUER = os.environ.get("JWT_ISSUER", "") or None

# ERR18 — `exp` est OBLIGATOIRE : un token sans expiration ne doit jamais etre
# accepte (il n'expirerait jamais). On exige aussi la presence des claims
# audience/emetteur quand le projet les configure.
_REQUIRED_CLAIMS = ["exp"]
if _JWT_AUDIENCE:
    _REQUIRED_CLAIMS.append("aud")
if _JWT_ISSUER:
    _REQUIRED_CLAIMS.append("iss")

_bearer_scheme = HTTPBearer(auto_error=False)


def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    Verifie le token JWT.
    Priorite : cookie httpOnly > Authorization: Bearer header.
    """
    # 1. Cookie httpOnly (inaccessible au JavaScript)
    token = request.cookies.get("access_token")

    # 2. Fallback : Authorization: Bearer (scripts, tests)
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decode_kwargs: dict = {
            "algorithms": [_ALGORITHM],
            # ERR18 — exige `exp` (et aud/iss si configures) + verifie l'expiration.
            "options": {"require": _REQUIRED_CLAIMS, "verify_exp": True},
        }
        if _JWT_AUDIENCE:
            decode_kwargs["audience"] = _JWT_AUDIENCE
        if _JWT_ISSUER:
            decode_kwargs["issuer"] = _JWT_ISSUER
        payload = jwt.decode(token, _DJANGO_SECRET_KEY, **decode_kwargs)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expire",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Un access token est requis",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def get_raw_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """Retourne le JETON brut (cookie httpOnly en priorite, puis Bearer).

    Utilise par l'agent (N86) pour relayer le JWT de l'appelant vers l'API
    Django interne lors d'une action d'ecriture, afin que Django applique
    lui-meme le scope societe et les permissions de role. Ne valide pas le
    jeton : c'est `verify_token` (deja en dependance) qui le fait.
    """
    token = request.cookies.get("access_token")
    if not token and credentials:
        token = credentials.credentials
    return token or ""
