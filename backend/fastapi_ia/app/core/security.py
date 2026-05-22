"""
Dépendance de vérification JWT pour FastAPI.
Valide les tokens émis par Django SimpleJWT (algorithme HS256, même SECRET_KEY).
"""
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError

# La même clé secrète que Django (partagée via variable d'environnement)
_DJANGO_SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
_ALGORITHM = "HS256"

_bearer_scheme = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """
    Vérifie le token JWT Bearer émis par Django SimpleJWT.
    Lève une 401 si le token est invalide, expiré, ou s'il ne s'agit pas d'un access token.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, _DJANGO_SECRET_KEY, algorithms=[_ALGORITHM])
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # S'assurer que c'est bien un access token (pas un refresh token)
    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Un access token est requis",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
