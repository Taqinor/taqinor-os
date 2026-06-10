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
        payload = jwt.decode(token, _DJANGO_SECRET_KEY, algorithms=[_ALGORITHM])
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
