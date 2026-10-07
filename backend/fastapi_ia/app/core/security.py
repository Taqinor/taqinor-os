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

# AUD409 — GARDE DE DEMARRAGE, miroir du garde Django
# (erp_agentique/settings/base.py:19-22) qui manquait totalement ici.
#
# MESURE sur la version EPINGLEE (PyJWT==2.13.0, requirements.txt) avant
# d'ecrire ce garde, pour ne rien affirmer d'invente : `jwt.decode(token, "")`
# n'accepte PAS un jeton force — PyJWT refuse une cle HMAC vide et leve
# `InvalidKeyError`. Le scenario « jeton signe avec une chaine vide accepte »
# n'est donc pas reproductible tel quel. Mais `InvalidKeyError` n'herite PAS
# d'`InvalidTokenError` : le `except` de `verify_token` ne l'attrape pas, et
# une omission d'environnement (unit systemd, nouveau deploiement, .env sans la
# cle) rendait le service 500 sur CHAQUE requete authentifiee — panne totale et
# opaque de l'agent SQL et de l'OCR, decouverte en production.
#
# Le garde reste donc necessaire pour deux raisons : rendre cette panne
# explicite et immediate au demarrage plutot que diffuse a l'execution, et ne
# pas faire dependre l'authentification d'un detail d'implementation de la
# librairie (une future version tolerant la cle vide rouvrirait, elle, un vrai
# contournement d'authentification). On echoue FERME au CHARGEMENT du module.
if not _DJANGO_SECRET_KEY:
    raise RuntimeError(
        "La variable d'environnement DJANGO_SECRET_KEY est obligatoire : le "
        "service IA verifie avec elle les JWT emis par Django. Une cle vide "
        "validerait n'importe quel jeton force."
    )

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


def _positive_int(value) -> int:
    try:
        number = int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def require_company_id(token_payload: dict) -> int:
    """Societe sur laquelle borner la requete — LE helper partage par l'agent
    SQL et l'OCR (AANA7).

    AANA7 (C-AANA-015) — la societe ACTIVE d'abord : Django emet le claim
    `active_company_id` apres une bascule de societe (XPLT19,
    authentication/active_company.py) et borne chaque requete Django a cette
    societe ; FastAPI doit lire la meme. Sans claim (ou claim invalide) : la
    societe d'attache `company_id`.

    ERR44 — un jeton sans societe valide (absente, 0, non numerique) est
    REFUSE (403) : le scoping par societe est la frontiere de securite, un
    company_id nul desactiverait tout le filtrage tenant."""
    company_id = (
        _positive_int(token_payload.get("active_company_id"))
        or _positive_int(token_payload.get("company_id"))
    )
    if not company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aucune entreprise associée à votre compte.",
        )
    return company_id


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
