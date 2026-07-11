"""Endpoints SSO SAML 2.0 par tenant (NTSEC2).

Publics (``AllowAny``, comme les autres endpoints tokenisés) et résolus par
``company_slug``. Dégradent proprement en 501 si ``python3-saml`` est absent, et
en 404 si la société n'a pas d'IdP SAML actif — le login local reste inchangé
dans tous les cas.

Flux :
* ``login/``    — SP-initiated : redirige vers l'IdP.
* ``acs/``      — Assertion Consumer Service (POST) : valide la signature contre
                  ``IdentityProvider.x509_cert``, refuse un rejeu, mappe les
                  attributs, résout/crée l'utilisateur, émet le cookie JWT.
* ``metadata/`` — métadonnées SP (XML auto-généré).
* ``sls/``      — Single Logout.
"""
import logging

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.response import Response

from authentication.models import Company

from . import saml as saml_mod
from .models import ConsumedAssertion, IdentityProvider
from .services import finalize_sso_login, resolve_or_provision_user

logger = logging.getLogger(__name__)


def _active_saml_idp(company_slug):
    """(company, idp) de l'IdP SAML ACTIF d'une société, ou (company, None)."""
    company = Company.objects.filter(slug=company_slug).first()
    if company is None:
        return None, None
    idp = IdentityProvider.objects.filter(
        company=company, protocol=IdentityProvider.PROTOCOL_SAML, actif=True
    ).first()
    return company, idp


def _unavailable():
    return Response(
        {'detail': 'SSO SAML non disponible (dépendance non installée).'},
        status=status.HTTP_501_NOT_IMPLEMENTED)


def _no_idp():
    return Response(
        {'detail': "Aucun fournisseur SAML actif pour cette société."},
        status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def saml_login(request, company_slug):
    """SP-initiated : redirige le navigateur vers l'IdP SAML."""
    company, idp = _active_saml_idp(company_slug)
    if idp is None:
        return _no_idp()
    if not saml_mod.saml_available():
        return _unavailable()
    try:
        auth = saml_mod.build_auth(idp, request)
        return Response({'redirect': auth.login()})
    except Exception:  # noqa: BLE001
        logger.exception('SAML login init failed')
        return Response(
            {'detail': 'Échec de l\'initialisation SAML.'},
            status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def saml_acs(request, company_slug):
    """Assertion Consumer Service — valide l'assertion et connecte l'utilisateur.

    Gère SP-initiated ET IdP-initiated (le POST arrive dans les deux cas). La
    signature est validée par la lib contre le ``x509_cert`` de l'IdP ;
    l'anti-rejeu refuse une assertion déjà consommée.
    """
    company, idp = _active_saml_idp(company_slug)
    if idp is None:
        return _no_idp()
    if not saml_mod.saml_available():
        return _unavailable()
    try:
        auth = saml_mod.build_auth(idp, request)
        auth.process_response()
        errors = auth.get_errors()
        if errors or not auth.is_authenticated():
            return Response(
                {'detail': 'Assertion SAML invalide.', 'errors': errors},
                status=status.HTTP_401_UNAUTHORIZED)

        # Anti-rejeu : l'assertion consommée est enregistrée (unique par
        # société) ; un rejeu (même id) est refusé.
        assertion_id = auth.get_last_assertion_id()
        if assertion_id:
            expire = _assertion_expiry(auth)
            _, created = ConsumedAssertion.objects.get_or_create(
                company=company, assertion_id=assertion_id,
                defaults={'expire_le': expire})
            if not created:
                return Response(
                    {'detail': 'Assertion SAML rejouée refusée.'},
                    status=status.HTTP_401_UNAUTHORIZED)

        attrs = auth.get_attributes() or {}
        email = _first_attr(attrs, idp, 'email') or auth.get_nameid()
        first_name = _first_attr(attrs, idp, 'prenom')
        last_name = _first_attr(attrs, idp, 'nom')
        groups = _list_attr(attrs, idp, 'groupes')

        user, _ = resolve_or_provision_user(
            idp, email=email, first_name=first_name, last_name=last_name,
            groups=groups)
        if user is None:
            return Response(
                {'detail': 'Utilisateur inconnu (auto-provisioning désactivé).'},
                status=status.HTTP_403_FORBIDDEN)
        if not user.is_active:
            return Response(
                {'detail': 'Compte désactivé.'},
                status=status.HTTP_403_FORBIDDEN)
        return finalize_sso_login(request, idp, user)
    except Exception:  # noqa: BLE001
        logger.exception('SAML ACS failed')
        return Response(
            {'detail': 'Échec du traitement de l\'assertion SAML.'},
            status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def saml_metadata(request, company_slug):
    """Métadonnées SP (XML) auto-générées pour cette société."""
    company, idp = _active_saml_idp(company_slug)
    if idp is None:
        return _no_idp()
    if not saml_mod.saml_available():
        return _unavailable()
    try:
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
        settings_obj = OneLogin_Saml2_Settings(
            saml_mod.build_saml_settings(idp, request), sp_validation_only=True)
        metadata = settings_obj.get_sp_metadata()
        return HttpResponse(metadata, content_type='text/xml')
    except Exception:  # noqa: BLE001
        logger.exception('SAML metadata failed')
        return Response(
            {'detail': 'Échec de génération des métadonnées SAML.'},
            status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def saml_sls(request, company_slug):
    """Single Logout Service — traite la déconnexion IdP (best-effort)."""
    company, idp = _active_saml_idp(company_slug)
    if idp is None:
        return _no_idp()
    if not saml_mod.saml_available():
        return _unavailable()
    try:
        auth = saml_mod.build_auth(idp, request)
        url = auth.process_slo(delete_session_cb=lambda: None)
        errors = auth.get_errors()
        if errors:
            return Response(
                {'detail': 'Erreur SLO SAML.', 'errors': errors},
                status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Déconnexion SAML traitée.',
                         'redirect': url})
    except Exception:  # noqa: BLE001
        logger.exception('SAML SLS failed')
        return Response(
            {'detail': 'Échec du traitement SLO SAML.'},
            status=status.HTTP_400_BAD_REQUEST)


def _first_attr(attrs, idp, logical):
    """Première valeur de l'attribut SAML mappé sur ``logical`` (email/nom…)."""
    key = (idp.attribute_map or {}).get(logical)
    if not key:
        return ''
    values = attrs.get(key) or []
    if isinstance(values, (list, tuple)):
        return values[0] if values else ''
    return values or ''


def _list_attr(attrs, idp, logical):
    """Liste de valeurs de l'attribut SAML mappé (ex. groupes)."""
    key = (idp.attribute_map or {}).get(logical)
    if not key:
        return []
    values = attrs.get(key) or []
    if isinstance(values, (list, tuple)):
        return list(values)
    return [values]


def _assertion_expiry(auth):
    """Borne de validité de la session (best-effort), sinon None."""
    try:
        expiry = auth.get_session_expiration()
        if expiry:
            from datetime import datetime, timezone as _tz
            return datetime.fromtimestamp(expiry, tz=_tz.utc)
    except Exception:  # noqa: BLE001
        pass
    return timezone.now()
