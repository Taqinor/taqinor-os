"""NTSEC5/6 — Service de provisioning SCIM 2.0 (Users + Groups).

Endpoints machine-à-machine authentifiés par un jeton porteur ``ScimToken``
dédié (jamais par le JWT humain). Chaque jeton est scopé société : il ne peut
lire/écrire QUE les comptes de sa propre société, et le ``company_slug`` de
l'URL doit correspondre à celle du jeton (sinon 404, jamais de fuite).

Toute la surface est FONDATION : on n'importe aucune app métier ; les rôles
sont appliqués via ``apps.roles.services`` (NTSEC6), jamais via ``roles.models``.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import CustomUser
from authentication.selectors import revoke_user_sessions

from .models import ScimToken

USER_SCHEMA = 'urn:ietf:params:scim:schemas:core:2.0:User'
LIST_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:ListResponse'
ERROR_SCHEMA = 'urn:ietf:params:scim:api:messages:2.0:Error'


def _error(detail, http_status):
    return Response(
        {'schemas': [ERROR_SCHEMA], 'detail': detail,
         'status': str(http_status)},
        status=http_status, content_type='application/scim+json')


def _authenticate(request, company_slug):
    """Résout la société depuis le jeton Bearer SCIM, ou renvoie une Response.

    Renvoie ``(company, None)`` si OK, sinon ``(None, Response)`` avec le bon
    code SCIM. Le slug de l'URL DOIT correspondre à la société du jeton.
    """
    from apps.publicapi.models import hash_key

    header = request.META.get('HTTP_AUTHORIZATION', '') or ''
    if not header.lower().startswith('bearer '):
        return None, _error('Jeton SCIM manquant.', status.HTTP_401_UNAUTHORIZED)
    raw = header[7:].strip()
    if not raw:
        return None, _error('Jeton SCIM manquant.', status.HTTP_401_UNAUTHORIZED)
    token = ScimToken.objects.filter(
        token_hash=hash_key(raw), actif=True).select_related('company').first()
    if token is None:
        return None, _error('Jeton SCIM invalide.', status.HTTP_401_UNAUTHORIZED)
    if token.company.slug != company_slug:
        # Slug ne correspond pas à la société du jeton : on ne révèle rien.
        return None, _error('Société inconnue.', status.HTTP_404_NOT_FOUND)
    ScimToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())
    return token.company, None


def scim_user_repr(user, request=None):
    """Représentation SCIM d'un ``CustomUser`` (schéma core 2.0 User)."""
    location = None
    if request is not None:
        location = request.build_absolute_uri().rstrip('/') + f'/{user.pk}'
    return {
        'schemas': [USER_SCHEMA],
        'id': str(user.pk),
        'userName': user.username,
        'name': {
            'givenName': user.first_name or '',
            'familyName': user.last_name or '',
        },
        'emails': ([{'value': user.email, 'primary': True}]
                   if user.email else []),
        'active': bool(user.is_active),
        'meta': {'resourceType': 'User',
                 **({'location': location} if location else {})},
    }


def _extract(body):
    """Extrait (username, email, given, family, active) d'un corps SCIM."""
    username = (body.get('userName') or '').strip()
    emails = body.get('emails') or []
    email = ''
    if isinstance(emails, list) and emails:
        first = emails[0]
        email = (first.get('value') if isinstance(first, dict) else first) or ''
    name = body.get('name') or {}
    given = (name.get('givenName') if isinstance(name, dict) else '') or ''
    family = (name.get('familyName') if isinstance(name, dict) else '') or ''
    active = body.get('active', True)
    return username, email.strip(), given, family, bool(active)


class ScimUsersView(APIView):
    """SCIM ``/Users`` : GET (liste + filtre userName), POST (création)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, company_slug):
        company, err = _authenticate(request, company_slug)
        if err is not None:
            return err
        qs = CustomUser.objects.filter(company=company).order_by('id')
        # Filtre SCIM minimal : ``userName eq "valeur"``.
        flt = request.query_params.get('filter')
        if flt:
            parts = flt.split(' ', 2)
            if len(parts) == 3 and parts[0] == 'userName' \
                    and parts[1].lower() == 'eq':
                qs = qs.filter(username__iexact=parts[2].strip('"'))
        resources = [scim_user_repr(u, request) for u in qs]
        return Response({
            'schemas': [LIST_SCHEMA],
            'totalResults': len(resources),
            'startIndex': 1,
            'itemsPerPage': len(resources),
            'Resources': resources,
        }, content_type='application/scim+json')

    def post(self, request, company_slug):
        company, err = _authenticate(request, company_slug)
        if err is not None:
            return err
        username, email, given, family, active = _extract(request.data or {})
        if not username:
            return _error('userName requis.', status.HTTP_400_BAD_REQUEST)
        existing = CustomUser.objects.filter(
            company=company, username__iexact=username).first()
        if existing is not None:
            return _error('Utilisateur déjà existant.',
                          status.HTTP_409_CONFLICT)
        # Société FORCÉE côté serveur (jamais depuis le corps SCIM).
        user = CustomUser.objects.create_user(
            username=username, email=email, company=company,
            first_name=given, last_name=family, is_active=active)
        # Compte fédéré : pas de mot de passe local utilisable (SSO only).
        user.set_unusable_password()
        user.save(update_fields=['password'])
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.SECURITY_ALERT, user=None, company=company,
                   detail=f'SCIM: compte {username} provisionné')
        except Exception:
            pass
        return Response(scim_user_repr(user, request),
                        status=status.HTTP_201_CREATED,
                        content_type='application/scim+json')


class ScimUserDetailView(APIView):
    """SCIM ``/Users/{id}`` : GET, PUT/PATCH (remplacement), DELETE (désactive)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def _get_user(self, company, pk):
        return CustomUser.objects.filter(company=company, pk=pk).first()

    def get(self, request, company_slug, pk):
        company, err = _authenticate(request, company_slug)
        if err is not None:
            return err
        user = self._get_user(company, pk)
        if user is None:
            return _error('Utilisateur introuvable.',
                          status.HTTP_404_NOT_FOUND)
        return Response(scim_user_repr(user, request),
                        content_type='application/scim+json')

    def _apply(self, request, company_slug, pk):
        company, err = _authenticate(request, company_slug)
        if err is not None:
            return err
        user = self._get_user(company, pk)
        if user is None:
            return _error('Utilisateur introuvable.',
                          status.HTTP_404_NOT_FOUND)
        body = request.data or {}
        username, email, given, family, active = _extract(body)
        fields = []
        if 'userName' in body and username:
            user.username = username
            fields.append('username')
        if 'emails' in body:
            user.email = email
            fields.append('email')
        if 'name' in body:
            user.first_name = given
            user.last_name = family
            fields += ['first_name', 'last_name']
        if 'active' in body:
            was_active = user.is_active
            user.is_active = active
            fields.append('is_active')
            if was_active and not active:
                revoke_user_sessions(user)
        if fields:
            user.save(update_fields=list(set(fields)))
        return Response(scim_user_repr(user, request),
                        content_type='application/scim+json')

    def put(self, request, company_slug, pk):
        return self._apply(request, company_slug, pk)

    def patch(self, request, company_slug, pk):
        return self._apply(request, company_slug, pk)

    def delete(self, request, company_slug, pk):
        company, err = _authenticate(request, company_slug)
        if err is not None:
            return err
        user = self._get_user(company, pk)
        if user is None:
            return _error('Utilisateur introuvable.',
                          status.HTTP_404_NOT_FOUND)
        # SCIM DELETE = désactivation (jamais suppression dure) + révocation.
        if user.is_active:
            user.is_active = False
            user.save(update_fields=['is_active'])
        revoke_user_sessions(user)
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.SECURITY_ALERT, user=None, company=company,
                   detail=f'SCIM: compte {user.username} déprovisionné')
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)
