"""NTAPI19 — OAuth2 « client_credentials » pour l'API publique.

Émission et vérification d'un jeton d'accès COURT (JWT HS256, signé avec la
``SECRET_KEY`` du serveur — ``PyJWT`` est déjà une dépendance du projet, aucune
nouvelle brique). Le jeton porte la société et les scopes ACCORDÉS ; il expire
(défaut 1 h) ; il n'est jamais stocké côté serveur (rien à révoquer ligne à
ligne — désactiver le ``OAuthClient`` suffit, et le jeton meurt de lui-même).

POURQUOI HS256 ET PAS UNE TABLE DE JETONS. Un jeton opaque en base exigerait
une lecture SQL par appel ET une purge ; un JWT signé se vérifie sans
entrée/sortie, ce qui est exactement ce qu'on veut sur le chemin chaud d'une
API. Le prix — on ne peut pas révoquer UN jeton — est payé par une durée de vie
courte et par la vérification, à CHAQUE appel, que le ``OAuthClient`` est
toujours actif (voir ``auth.OAuthBearerAuthentication``) : désactiver un client
coupe donc l'accès immédiatement, même si un jeton non expiré circule encore.
"""
from __future__ import annotations

import time

import jwt
from django.conf import settings

# Durée de vie par défaut du jeton (secondes). Volontairement courte : c'est
# TOUT l'intérêt du flot face à une clé d'API permanente.
DEFAULT_TOKEN_TTL_SECONDS = 3600
ALGORITHME = 'HS256'
# Marqueur de type : un jeton de session (SimpleJWT) ne doit JAMAIS pouvoir
# être présenté comme un jeton d'API publique, ni l'inverse. Les deux sont
# signés avec la même SECRET_KEY — sans ce marqueur vérifié, un jeton d'accès
# utilisateur ouvrirait l'API publique avec les scopes qu'il n'a pas.
TYPE_JETON = 'publicapi_client_credentials'
GRANT_TYPE = 'client_credentials'


def ttl_seconds():
    return int(getattr(settings, 'PUBLIC_API_OAUTH_TOKEN_TTL',
                       DEFAULT_TOKEN_TTL_SECONDS) or DEFAULT_TOKEN_TTL_SECONDS)


def emettre_token(oauth_client, *, scopes=None, now=None):
    """Émet un JWT court pour ``oauth_client``. Renvoie ``(jeton, expire_in)``.

    ``scopes`` (optionnel) restreint le jeton à un SOUS-ENSEMBLE des scopes du
    client — jamais à autre chose : tout scope demandé hors de la dotation du
    client est silencieusement écarté (un client ne s'auto-élève pas).
    """
    maintenant = int(now if now is not None else time.time())
    accordes = list(oauth_client.scopes or [])
    if scopes:
        accordes = [s for s in scopes if s in accordes]
    duree = ttl_seconds()
    charge = {
        'typ': TYPE_JETON,
        'sub': oauth_client.client_id,
        'company_id': oauth_client.company_id,
        'scopes': accordes,
        'iat': maintenant,
        'exp': maintenant + duree,
    }
    jeton = jwt.encode(charge, settings.SECRET_KEY, algorithm=ALGORITHME)
    # PyJWT < 2 renvoyait des bytes ; on normalise sans dépendre de la version.
    if isinstance(jeton, bytes):
        jeton = jeton.decode('utf-8')
    return jeton, duree


class JetonInvalide(Exception):
    """Jeton absent, illisible, expiré, ou d'un type qui n'est pas le nôtre."""


def decoder_token(jeton):
    """Décode et VALIDE un jeton. Lève ``JetonInvalide`` sinon.

    Valide la signature, l'expiration (PyJWT s'en charge) ET le marqueur de
    type — sans ce dernier contrôle, un jeton de session utilisateur, signé
    avec la même clé, serait accepté ici."""
    try:
        charge = jwt.decode(jeton, settings.SECRET_KEY,
                            algorithms=[ALGORITHME])
    except jwt.ExpiredSignatureError:
        raise JetonInvalide('Jeton expiré.')
    except jwt.InvalidTokenError:
        raise JetonInvalide('Jeton invalide.')
    if charge.get('typ') != TYPE_JETON:
        raise JetonInvalide('Jeton invalide.')
    if not charge.get('sub') or not charge.get('company_id'):
        raise JetonInvalide('Jeton invalide.')
    return charge


def scopes_effectifs(charge, api_key):
    """Scopes RÉELLEMENT applicables : intersection jeton ∩ clé compagnon.

    Le jeton dit ce qui a été accordé À L'ÉMISSION ; la clé compagnon dit ce
    qui est accordé MAINTENANT. Retirer un scope au client doit prendre effet
    sans attendre l'expiration des jetons déjà émis — d'où l'intersection, et
    jamais une simple lecture du jeton."""
    du_jeton = set(charge.get('scopes') or [])
    de_la_cle = set(api_key.scopes or [])
    return sorted(du_jeton & de_la_cle)
