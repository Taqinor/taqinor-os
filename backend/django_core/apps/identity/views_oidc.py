"""Endpoints SSO OIDC (Authorization Code + PKCE) par tenant (NTSEC3).

Publics (``AllowAny``), résolus par ``company_slug``. Dégradent en 501 sans le
socle OIDC (requests + PyJWT) et en 404 sans IdP OIDC actif ; login local
inchangé.

* ``login/``    — crée un ``OidcAuthState`` (state+nonce+PKCE) et renvoie l'URL
                  de redirection vers l'``authorization_endpoint``.
* ``callback/`` — valide le ``state``, échange le ``code``, valide l'``id_token``
                  (signature + nonce + aud + exp), mappe les claims,
                  résout/crée l'utilisateur et émet le cookie JWT + session.
"""
import logging

from rest_framework import permissions, status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.response import Response

from authentication.models import Company

from . import oidc as oidc_mod
from .models import IdentityProvider, OidcAuthState
from .services import finalize_sso_login, resolve_or_provision_user

logger = logging.getLogger(__name__)


def _active_oidc_idp(company_slug):
    company = Company.objects.filter(slug=company_slug).first()
    if company is None:
        return None, None
    idp = IdentityProvider.objects.filter(
        company=company, protocol=IdentityProvider.PROTOCOL_OIDC, actif=True
    ).first()
    return company, idp


def _redirect_uri(request, company_slug):
    scheme = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    return (f'{scheme}://{host}/api/django/identity/oidc/'
            f'{company_slug}/callback/')


def _unavailable():
    return Response(
        {'detail': 'SSO OIDC non disponible (dépendance non installée).'},
        status=status.HTTP_501_NOT_IMPLEMENTED)


def _no_idp():
    return Response(
        {'detail': "Aucun fournisseur OIDC actif pour cette société."},
        status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def oidc_login(request, company_slug):
    """Démarre le flow : crée l'état PKCE et renvoie l'URL de redirection IdP."""
    company, idp = _active_oidc_idp(company_slug)
    if idp is None:
        return _no_idp()
    if not oidc_mod.oidc_available():
        return _unavailable()
    try:
        conf = oidc_mod.discover(idp)
        if not conf.get('authorization_endpoint'):
            return Response(
                {'detail': "authorization_endpoint OIDC introuvable."},
                status=status.HTTP_400_BAD_REQUEST)
        verifier, challenge = oidc_mod.gen_pkce_pair()
        state = oidc_mod.gen_state()
        nonce = oidc_mod.gen_nonce()
        OidcAuthState.objects.create(
            company=company, state=state, nonce=nonce, code_verifier=verifier)
        url = oidc_mod.build_authorization_url(
            idp, conf, redirect_uri=_redirect_uri(request, company_slug),
            state=state, nonce=nonce, code_challenge=challenge)
        return Response({'redirect': url})
    except Exception:  # noqa: BLE001
        logger.exception('OIDC login init failed')
        return Response(
            {'detail': "Échec de l'initialisation OIDC."},
            status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def oidc_callback(request, company_slug):
    """Reçoit le ``code`` + ``state``, valide et connecte l'utilisateur."""
    company, idp = _active_oidc_idp(company_slug)
    if idp is None:
        return _no_idp()
    if not oidc_mod.oidc_available():
        return _unavailable()

    code = request.GET.get('code')
    state = request.GET.get('state')
    if not code or not state:
        return Response(
            {'detail': 'Paramètres OIDC manquants (code/state).'},
            status=status.HTTP_400_BAD_REQUEST)

    # Consommation à USAGE UNIQUE de l'état (anti-CSRF + anti-rejeu du code).
    auth_state = OidcAuthState.objects.filter(
        company=company, state=state, used=False).first()
    if auth_state is None:
        return Response(
            {'detail': 'État OIDC invalide ou déjà consommé.'},
            status=status.HTTP_401_UNAUTHORIZED)
    auth_state.used = True
    auth_state.save(update_fields=['used'])

    try:
        conf = oidc_mod.discover(idp)
        tokens = oidc_mod.exchange_code(
            idp, conf, code=code,
            redirect_uri=_redirect_uri(request, company_slug),
            code_verifier=auth_state.code_verifier)
        id_token = tokens.get('id_token')
        if not id_token:
            return Response(
                {'detail': "Réponse OIDC sans id_token."},
                status=status.HTTP_401_UNAUTHORIZED)
        claims = oidc_mod.validate_id_token(
            idp, conf, id_token, nonce=auth_state.nonce)
    except ValueError as exc:
        return Response(
            {'detail': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception:  # noqa: BLE001
        logger.exception('OIDC callback failed')
        return Response(
            {'detail': 'Échec du traitement OIDC.'},
            status=status.HTTP_400_BAD_REQUEST)

    email = _claim(claims, idp, 'email') or claims.get('email')
    first_name = _claim(claims, idp, 'prenom') or claims.get('given_name', '')
    last_name = _claim(claims, idp, 'nom') or claims.get('family_name', '')
    groups = _claim_list(claims, idp, 'groupes')

    user, _ = resolve_or_provision_user(
        idp, email=email, first_name=first_name, last_name=last_name,
        groups=groups)
    if user is None:
        return Response(
            {'detail': 'Utilisateur inconnu (auto-provisioning désactivé).'},
            status=status.HTTP_403_FORBIDDEN)
    if not user.is_active:
        return Response(
            {'detail': 'Compte désactivé.'}, status=status.HTTP_403_FORBIDDEN)
    return finalize_sso_login(request, idp, user)


def _claim(claims, idp, logical):
    key = (idp.attribute_map or {}).get(logical)
    if not key:
        return ''
    return claims.get(key, '')


def _claim_list(claims, idp, logical):
    key = (idp.attribute_map or {}).get(logical)
    if not key:
        return []
    value = claims.get(key)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
