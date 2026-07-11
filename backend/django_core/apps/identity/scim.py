"""Socle SCIM 2.0 (NTSEC5/6) : authentification par jeton + (dé)sérialisation.

Le service SCIM est authentifié par un ``ScimToken`` porteur dédié (jamais un
JWT humain). Les représentations suivent le schéma SCIM
``urn:ietf:params:scim:schemas:core:2.0:User``.
"""
from django.utils import timezone
from rest_framework.parsers import JSONParser

SCIM_USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
SCIM_GROUP_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:Group'
SCIM_LIST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:ListResponse'
SCIM_ERROR_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:Error'


class ScimJSONParser(JSONParser):
    """Parse le ``Content-Type: application/scim+json`` des requêtes SCIM.

    Identique au ``JSONParser`` DRF mais négocie le media type SCIM (les IdP
    postent en ``application/scim+json``). Le ``application/json`` reste géré
    par le ``JSONParser`` standard aussi listé sur les vues SCIM.
    """
    media_type = 'application/scim+json'


def authenticate_scim(request, company):
    """Résout et valide le ``ScimToken`` porteur d'une requête SCIM.

    Retourne le ``ScimToken`` actif de la société si le header
    ``Authorization: Bearer <token>`` est valide, sinon None. Met à jour
    ``last_used_at`` best-effort.
    """
    from .models import ScimToken, hash_scim_token

    header = request.META.get('HTTP_AUTHORIZATION', '') or ''
    if not header.lower().startswith('bearer '):
        return None
    raw = header[7:].strip()
    if not raw:
        return None
    token = ScimToken.objects.filter(
        company=company, token_hash=hash_scim_token(raw), actif=True).first()
    if token is None:
        return None
    try:
        ScimToken.objects.filter(pk=token.pk).update(
            last_used_at=timezone.now())
    except Exception:  # noqa: BLE001 — best-effort
        pass
    return token


def user_to_scim(user, request=None):
    """Représentation SCIM ``User`` d'un ``CustomUser``."""
    location = ''
    if request is not None:
        location = request.build_absolute_uri()
    given = user.first_name or ''
    family = user.last_name or ''
    formatted = (f'{given} {family}').strip()
    return {
        'schemas': [SCIM_USER_SCHEMA],
        'id': str(user.pk),
        'userName': user.username,
        'name': {
            'givenName': given,
            'familyName': family,
            'formatted': formatted,
        },
        'displayName': formatted or user.username,
        'emails': ([{'value': user.email, 'primary': True}]
                   if user.email else []),
        'active': bool(user.is_active),
        'meta': {'resourceType': 'User', 'location': location},
    }


def group_to_scim(mapping):
    """Représentation SCIM ``Group`` d'un ``ScimGroupMapping``.

    Les membres = les utilisateurs de la société portant le rôle mappé
    (source de vérité = le rôle appliqué).
    """
    members = []
    try:
        from authentication.models import CustomUser
        users = CustomUser.objects.filter(
            company=mapping.company, role_id=mapping.role_id, is_active=True)
        members = [{'value': str(u.pk), 'display': u.username} for u in users]
    except Exception:  # noqa: BLE001
        members = []
    return {
        'schemas': [SCIM_GROUP_SCHEMA],
        'id': str(mapping.pk),
        'displayName': mapping.scim_group_name,
        'members': members,
        'meta': {'resourceType': 'Group'},
    }


def scim_error(detail, status_code):
    """Enveloppe d'erreur au schéma SCIM."""
    return {
        'schemas': [SCIM_ERROR_SCHEMA],
        'detail': detail,
        'status': str(status_code),
    }


def list_response(resources, total=None, start_index=1):
    """Enveloppe ``ListResponse`` SCIM."""
    total = len(resources) if total is None else total
    return {
        'schemas': [SCIM_LIST_SCHEMA],
        'totalResults': total,
        'startIndex': start_index,
        'itemsPerPage': len(resources),
        'Resources': resources,
    }


def parse_username_filter(filter_expr):
    """Extrait la valeur d'un filtre SCIM ``userName eq "x"`` (ou None)."""
    if not filter_expr:
        return None
    import re
    m = re.search(r'userName\s+eq\s+"([^"]+)"', filter_expr, re.IGNORECASE)
    return m.group(1) if m else None
