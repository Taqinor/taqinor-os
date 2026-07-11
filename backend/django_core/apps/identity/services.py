"""Services d'orchestration de la fondation identité (NTSEC).

Finalisation commune d'une connexion fédérée (SAML NTSEC2 / OIDC NTSEC3 / JIT
NTSEC7) : résolution/création de l'utilisateur scopé société, application du
rôle par défaut ou des groupes SSO, émission des cookies JWT + création d'une
``UserSession`` révocable, et journalisation d'audit ``SSO_LOGIN``.

Ces services sont des fonctions FINES : ils réutilisent la machinerie
d'``authentication`` (émission de jeton, cookies, session) — jamais de
duplication du flux de login local.
"""
import logging

logger = logging.getLogger(__name__)


def resolve_or_provision_user(idp, *, email, first_name='', last_name='',
                              groups=None):
    """Résout l'utilisateur d'une société pour une identité fédérée.

    Recherche un ``CustomUser`` de la société de l'IdP par email (username =
    email en repli). Si absent et ``idp.auto_provision``, crée un compte
    inactif-au-mot-de-passe (mot de passe inutilisable — l'accès passe par le
    SSO) portant ``idp.default_role``. Applique aussi les groupes SSO (NTSEC7,
    best-effort). Retourne ``(user, created)`` ou ``(None, False)`` si absent et
    pas d'auto-provision.
    """
    from authentication.models import CustomUser

    email = (email or '').strip().lower()
    if not email:
        return None, False
    company = idp.company

    user = (CustomUser.objects.filter(company=company, email__iexact=email)
            .first())
    if user is None:
        user = (CustomUser.objects.filter(company=company, username__iexact=email)
                .first())

    created = False
    if user is None:
        if not idp.auto_provision:
            return None, False
        user = CustomUser(
            username=email, email=email,
            first_name=(first_name or '')[:150],
            last_name=(last_name or '')[:150],
            company=company,
            role_id=idp.default_role_id or None,
        )
        user.set_unusable_password()
        user.save()
        created = True

    # NTSEC7 — application des groupes SSO à chaque connexion (best-effort).
    apply_sso_groups(idp, user, groups)
    return user, created


def apply_sso_groups(idp, user, groups):
    """Applique les rôles issus des groupes SSO (NTSEC7).

    Placeholder de fondation câblé pleinement en NTSEC7 : ici, best-effort,
    n'échoue jamais. Sans mapping de groupe, retombe sur ``default_role`` pour
    un compte fraîchement provisionné (déjà posé à la création).
    """
    try:
        if not groups:
            return
        # Le mapping groupe→rôle détaillé (ScimGroupMapping) est branché en
        # NTSEC7 ; on ne fait rien de plus ici pour rester additif.
    except Exception:  # noqa: BLE001 — best-effort
        logger.debug('apply_sso_groups failed', exc_info=True)


def finalize_sso_login(request, idp, user):
    """Émet les cookies JWT + crée la ``UserSession`` + journalise ``SSO_LOGIN``.

    Réutilise strictement la machinerie d'``authentication`` (mêmes claims,
    mêmes cookies, même traçage de session que le login local). Retourne un
    ``rest_framework.response.Response`` avec les cookies posés.
    """
    from rest_framework.response import Response

    from authentication.serializers import CustomTokenObtainPairSerializer
    from authentication.views import _record_session, _set_auth_cookies

    refresh = CustomTokenObtainPairSerializer.get_token(user)
    access = refresh.access_token
    response = Response({
        'detail': 'Connexion SSO réussie.',
        'company_id': user.company_id,
        'username': user.username,
    })
    _set_auth_cookies(response, str(access), str(refresh))
    # Session révocable tracée par le jti du refresh (best-effort).
    _record_session(user, str(refresh), request)
    _audit_sso_login(user, idp)
    return response


def _audit_sso_login(user, idp):
    """Journalise l'action d'audit ``SSO_LOGIN`` (best-effort, NTSEC18)."""
    try:
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record

        action = getattr(AuditLog.Action, 'SSO_LOGIN', AuditLog.Action.LOGIN)
        record(
            action, user=user, actor_username=user.username,
            company=user.company,
            detail=f'Connexion SSO ({idp.get_protocol_display()} · {idp.nom}).')
    except Exception:  # noqa: BLE001 — best-effort : jamais bloquer le login
        logger.debug('SSO login audit failed', exc_info=True)
