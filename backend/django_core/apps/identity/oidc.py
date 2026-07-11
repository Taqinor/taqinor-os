"""Câblage OIDC (Authorization Code + PKCE) par tenant (NTSEC3), flow maison.

Utilise ``requests`` (découverte + échange de code) et ``PyJWT`` (validation de
l'``id_token`` : signature via JWKS, ``nonce``/``aud``/``exp``). Ces deux libs
sont déjà présentes (dépendances de simplejwt/anymail). ``oidc_available()``
garde le tout : sans ``requests``/``jwt`` la couche dégrade proprement en 501.
"""
import base64
import hashlib
import logging
import secrets

logger = logging.getLogger(__name__)


def oidc_available():
    """True si le socle OIDC (requests + PyJWT) est disponible."""
    try:
        import jwt  # noqa: F401
        import requests  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def gen_pkce_pair():
    """Génère (code_verifier, code_challenge) PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')
    return verifier, challenge


def gen_state():
    return secrets.token_urlsafe(32)


def gen_nonce():
    return secrets.token_urlsafe(32)


def discover(idp):
    """Résout (authorization_endpoint, token_endpoint, jwks_uri, issuer).

    Depuis ``metadata_url`` (.well-known/openid-configuration) si fourni, sinon
    depuis les champs bruts de l'IdP (``sso_url`` = authorization_endpoint).
    Best-effort réseau : en cas d'échec de découverte, retombe sur les champs
    bruts.
    """
    authorization = idp.sso_url
    token = ''
    jwks = ''
    issuer = idp.entity_id
    if idp.metadata_url:
        try:
            import requests
            resp = requests.get(idp.metadata_url, timeout=10)
            resp.raise_for_status()
            doc = resp.json()
            authorization = doc.get('authorization_endpoint') or authorization
            token = doc.get('token_endpoint') or token
            jwks = doc.get('jwks_uri') or jwks
            issuer = doc.get('issuer') or issuer
        except Exception:  # noqa: BLE001 — repli sur les champs bruts
            logger.debug('OIDC discovery failed', exc_info=True)
    return {
        'authorization_endpoint': authorization,
        'token_endpoint': token,
        'jwks_uri': jwks,
        'issuer': issuer,
    }


def build_authorization_url(idp, conf, *, redirect_uri, state, nonce,
                            code_challenge):
    """Construit l'URL de redirection vers l'``authorization_endpoint``."""
    from urllib.parse import urlencode
    params = {
        'response_type': 'code',
        'client_id': idp.client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid email profile',
        'state': state,
        'nonce': nonce,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }
    endpoint = conf['authorization_endpoint']
    sep = '&' if '?' in endpoint else '?'
    return f'{endpoint}{sep}{urlencode(params)}'


def exchange_code(idp, conf, *, code, redirect_uri, code_verifier):
    """Échange le ``code`` contre les jetons au ``token_endpoint``."""
    import requests
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': idp.client_id,
        'code_verifier': code_verifier,
    }
    if idp.client_secret:
        data['client_secret'] = idp.client_secret
    resp = requests.post(conf['token_endpoint'], data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def validate_id_token(idp, conf, id_token, *, nonce):
    """Valide l'``id_token`` (signature JWKS + nonce + aud + exp) → claims.

    Lève ``ValueError`` si invalide. La signature est vérifiée via le JWKS de
    l'IdP quand ``jwks_uri`` est connu ; sinon, si un ``x509_cert`` PEM est
    fourni, on l'utilise ; à défaut, on refuse (jamais de validation sans
    vérification de signature).
    """
    import jwt

    audience = idp.client_id or None
    options = {'require': ['exp', 'iat']}
    key, algorithms = _signing_key(idp, conf, id_token)
    if key is None:
        raise ValueError('Clé de signature id_token introuvable.')
    try:
        claims = jwt.decode(
            id_token, key=key, algorithms=algorithms,
            audience=audience, options=options,
            issuer=conf.get('issuer') or None)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f'id_token invalide : {exc}') from exc

    if nonce and claims.get('nonce') != nonce:
        raise ValueError('nonce id_token invalide (anti-rejeu).')
    return claims


def _signing_key(idp, conf, id_token):
    """(clé, algorithmes) pour valider l'id_token — JWKS puis x509_cert PEM."""
    import jwt

    jwks_uri = conf.get('jwks_uri')
    if jwks_uri:
        try:
            client = jwt.PyJWKClient(jwks_uri)
            signing_key = client.get_signing_key_from_jwt(id_token)
            return signing_key.key, ['RS256', 'RS384', 'RS512', 'ES256']
        except Exception:  # noqa: BLE001
            logger.debug('OIDC JWKS resolution failed', exc_info=True)
    if idp.x509_cert:
        try:
            from cryptography.x509 import load_pem_x509_certificate
            pem = idp.x509_cert.encode('utf-8')
            cert = load_pem_x509_certificate(pem)
            return cert.public_key(), ['RS256', 'RS384', 'RS512', 'ES256']
        except Exception:  # noqa: BLE001
            logger.debug('OIDC x509 cert load failed', exc_info=True)
    return None, []
