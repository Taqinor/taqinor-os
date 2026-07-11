"""Endpoints SCIM 2.0 — Users (NTSEC5) & Groups (NTSEC6).

Authentifiés par un ``ScimToken`` porteur dédié (jamais un JWT humain), scopés
société par ``company_slug``. Un jeton invalide → 401. ``DELETE``/``active=false``
désactive le ``CustomUser`` ET révoque ses ``UserSession``.
"""
import logging

from rest_framework import permissions, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import Company, CustomUser, UserSession

from . import scim
from .models import ScimGroupMapping

logger = logging.getLogger(__name__)

SCIM_CONTENT_TYPE = 'application/scim+json'


def _revoke_user_sessions(user):
    """Révoque toutes les sessions actives d'un utilisateur (best-effort).

    Réutilise le blacklisting du refresh (``authentication.views``) : la
    session sort de la liste ET son jeton ne peut plus rafraîchir.
    """
    try:
        from authentication.views import _blacklist_refresh_jti
        sessions = UserSession.objects.filter(user=user, revoked=False)
        for sess in sessions:
            _blacklist_refresh_jti(sess.jti)
        sessions.update(revoked=True)
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug('SCIM session revoke failed', exc_info=True)


class _ScimBase(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    # Les IdP postent en application/scim+json ; on accepte aussi application/
    # json standard.
    parser_classes = [scim.ScimJSONParser, JSONParser]

    def _resolve(self, request, company_slug):
        """(company, token) ou lève une réponse 401/404 via ``self._deny``."""
        company = Company.objects.filter(slug=company_slug).first()
        if company is None:
            return None, None
        token = scim.authenticate_scim(request, company)
        return company, token

    def _unauthorized(self):
        return Response(
            scim.scim_error('Jeton SCIM invalide.', 401),
            status=status.HTTP_401_UNAUTHORIZED,
            content_type=SCIM_CONTENT_TYPE)

    def _not_found(self, what='Ressource'):
        return Response(
            scim.scim_error(f'{what} introuvable.', 404),
            status=status.HTTP_404_NOT_FOUND,
            content_type=SCIM_CONTENT_TYPE)


class ScimUsersView(_ScimBase):
    """GET (list+filter) / POST (create) sur ``scim/v2/<slug>/Users``."""

    def get(self, request, company_slug):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        qs = CustomUser.objects.filter(company=company)
        username = scim.parse_username_filter(request.GET.get('filter'))
        if username:
            qs = qs.filter(username__iexact=username)
        resources = [scim.user_to_scim(u) for u in qs.order_by('id')]
        return Response(
            scim.list_response(resources),
            content_type=SCIM_CONTENT_TYPE)

    def post(self, request, company_slug):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        data = request.data or {}
        username = (data.get('userName') or '').strip()
        if not username:
            return Response(
                scim.scim_error('userName requis.', 400),
                status=status.HTTP_400_BAD_REQUEST,
                content_type=SCIM_CONTENT_TYPE)
        email = _primary_email(data) or username
        name = data.get('name') or {}
        existing = CustomUser.objects.filter(
            company=company, username__iexact=username).first()
        if existing is not None:
            return Response(
                scim.scim_error('Utilisateur déjà existant.', 409),
                status=status.HTTP_409_CONFLICT,
                content_type=SCIM_CONTENT_TYPE)
        user = CustomUser(
            username=username, email=email,
            first_name=(name.get('givenName') or '')[:150],
            last_name=(name.get('familyName') or '')[:150],
            company=company,
            is_active=data.get('active', True),
        )
        user.set_unusable_password()
        user.save()
        _audit_scim(user, provision=True)
        return Response(
            scim.user_to_scim(user, request),
            status=status.HTTP_201_CREATED,
            content_type=SCIM_CONTENT_TYPE)


class ScimUserDetailView(_ScimBase):
    """GET / PUT / PATCH / DELETE sur ``scim/v2/<slug>/Users/<id>``."""

    def _get_user(self, company, pk):
        return CustomUser.objects.filter(company=company, pk=pk).first()

    def get(self, request, company_slug, pk):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        user = self._get_user(company, pk)
        if user is None:
            return self._not_found('Utilisateur')
        return Response(
            scim.user_to_scim(user, request), content_type=SCIM_CONTENT_TYPE)

    def put(self, request, company_slug, pk):
        return self._replace(request, company_slug, pk)

    def patch(self, request, company_slug, pk):
        return self._replace(request, company_slug, pk)

    def _replace(self, request, company_slug, pk):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        user = self._get_user(company, pk)
        if user is None:
            return self._not_found('Utilisateur')
        data = request.data or {}
        fields = []
        active = _extract_active(data)
        if active is not None and active != user.is_active:
            user.is_active = active
            fields.append('is_active')
            if not active:
                _revoke_user_sessions(user)
                _audit_scim(user, provision=False)
        name = data.get('name') or {}
        if 'givenName' in name:
            user.first_name = (name.get('givenName') or '')[:150]
            fields.append('first_name')
        if 'familyName' in name:
            user.last_name = (name.get('familyName') or '')[:150]
            fields.append('last_name')
        email = _primary_email(data)
        if email:
            user.email = email
            fields.append('email')
        if fields:
            user.save(update_fields=list(set(fields)))
        return Response(
            scim.user_to_scim(user, request), content_type=SCIM_CONTENT_TYPE)

    def delete(self, request, company_slug, pk):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        user = self._get_user(company, pk)
        if user is None:
            return self._not_found('Utilisateur')
        # DELETE SCIM = désactivation (jamais de suppression dure) + révocation
        # des sessions.
        if user.is_active:
            user.is_active = False
            user.save(update_fields=['is_active'])
            _revoke_user_sessions(user)
            _audit_scim(user, provision=False)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ScimGroupsView(_ScimBase):
    """GET (list) / POST (create/apply members) sur ``scim/v2/<slug>/Groups``.

    Un « groupe » SCIM correspond à un ``ScimGroupMapping`` (nom de groupe →
    rôle). L'ajout d'un membre applique le rôle mappé sur le ``CustomUser`` (via
    ``roles/services.py``, jamais d'accès direct au FK) ; POST sans membres crée
    seulement le groupe visible.
    """

    def get(self, request, company_slug):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        resources = [scim.group_to_scim(m)
                     for m in ScimGroupMapping.objects.filter(company=company)]
        return Response(
            scim.list_response(resources), content_type=SCIM_CONTENT_TYPE)

    def post(self, request, company_slug):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        data = request.data or {}
        name = (data.get('displayName') or '').strip()
        mapping = ScimGroupMapping.objects.filter(
            company=company, scim_group_name=name).first()
        if mapping is None:
            return Response(
                scim.scim_error(
                    'Groupe SCIM non mappé à un rôle (créez le mapping via '
                    "l'admin).", 404),
                status=status.HTTP_404_NOT_FOUND,
                content_type=SCIM_CONTENT_TYPE)
        for member in (data.get('members') or []):
            _apply_role_to_member(company, mapping, member, add=True)
        return Response(
            scim.group_to_scim(mapping), status=status.HTTP_200_OK,
            content_type=SCIM_CONTENT_TYPE)


class ScimGroupDetailView(_ScimBase):
    """PATCH sur ``scim/v2/<slug>/Groups/<id>`` — add/remove members → rôle."""

    def _get_mapping(self, company, pk):
        return ScimGroupMapping.objects.filter(company=company, pk=pk).first()

    def get(self, request, company_slug, pk):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        mapping = self._get_mapping(company, pk)
        if mapping is None:
            return self._not_found('Groupe')
        return Response(
            scim.group_to_scim(mapping), content_type=SCIM_CONTENT_TYPE)

    def patch(self, request, company_slug, pk):
        company, token = self._resolve(request, company_slug)
        if company is None:
            return self._not_found('Société')
        if token is None:
            return self._unauthorized()
        mapping = self._get_mapping(company, pk)
        if mapping is None:
            return self._not_found('Groupe')
        for op in (request.data or {}).get('Operations') or []:
            if not isinstance(op, dict):
                continue
            verb = (op.get('op') or '').lower()
            value = op.get('value')
            members = value if isinstance(value, list) else \
                (value.get('members') if isinstance(value, dict) else [])
            for member in (members or []):
                _apply_role_to_member(
                    company, mapping, member, add=(verb != 'remove'))
        return Response(
            scim.group_to_scim(mapping), content_type=SCIM_CONTENT_TYPE)


def _apply_role_to_member(company, mapping, member, *, add):
    """Applique/retire le rôle mappé sur le membre SCIM (via roles/services)."""
    from apps.roles import services as role_services

    value = member.get('value') if isinstance(member, dict) else member
    if not value:
        return
    user = CustomUser.objects.filter(company=company, pk=value).first()
    if user is None:
        user = CustomUser.objects.filter(
            company=company, username__iexact=str(value)).first()
    if user is None:
        return
    if add:
        role_services.assign_role(user, mapping.role)
    else:
        role_services.revoke_role(user, mapping.role)


def _primary_email(data):
    emails = data.get('emails') or []
    if not isinstance(emails, list):
        return ''
    primary = [e for e in emails if isinstance(e, dict) and e.get('primary')]
    chosen = primary or [e for e in emails if isinstance(e, dict)]
    return (chosen[0].get('value') if chosen else '') or ''


def _extract_active(data):
    """Valeur ``active`` d'un PUT SCIM ou d'un PATCH (Operations)."""
    if 'active' in data:
        return bool(data['active'])
    ops = data.get('Operations') or []
    for op in ops:
        if not isinstance(op, dict):
            continue
        path = (op.get('path') or '').lower()
        if path == 'active':
            return bool(op.get('value'))
        value = op.get('value')
        if isinstance(value, dict) and 'active' in value:
            return bool(value['active'])
    return None


def _audit_scim(user, *, provision):
    try:
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record
        if provision:
            action = getattr(
                AuditLog.Action, 'SCIM_PROVISION', AuditLog.Action.CREATE)
            detail = 'Provisioning SCIM'
        else:
            action = getattr(
                AuditLog.Action, 'SCIM_DEPROVISION', AuditLog.Action.UPDATE)
            detail = 'Désactivation SCIM'
        record(action, user=None, company=user.company,
               instance=user, detail=detail)
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug('SCIM audit failed', exc_info=True)
