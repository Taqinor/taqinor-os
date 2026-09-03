"""
Authentification JWT via httpOnly cookie.
Remplace la lecture du token dans l'en-tete Authorization.
"""
from django.contrib.auth import get_user_model
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken


# AUD404 — nom du claim de session d'impersonation, MIROIR de
# `apps.adminops.impersonation_service.CLAIM_SESSION`. Il est redéclaré ici — et
# pas importé — parce que `authentication` est une app de FONDATION : importer
# `impersonation_service` fait remonter, par
# `adminops → notifications.services → {ventes, sav, stock, crm, reporting}`, une
# chaîne qui casse le contrat import-linter « the core foundation app imports
# downward only » (mesuré : 5 contrats rouges). Le registre d'applications Django
# donne le modèle sans créer la moindre arête d'import. La divergence des deux
# constantes est interdite par un test dédié dans `apps/adminops/tests/`.
_IMPERSONATION_CLAIM = 'imp'


def _impersonation_revoquee(validated_token):
    """True si le jeton porte un claim de session d'impersonation qui n'est
    PLUS active (terminée, refusée, expirée, consentement retiré).

    FAIL-CLOSED : un claim présent dont la ligne de session est introuvable est
    traité comme révoqué — un jeton d'impersonation sans session vivante ne doit
    jamais authentifier. Aucune requête pour un jeton ordinaire (sans claim).
    """
    session_id = validated_token.get(_IMPERSONATION_CLAIM) \
        if validated_token else None
    if not session_id:
        return False
    from django.apps import apps as django_apps
    session_model = django_apps.get_model('adminops', 'SessionImpersonation')
    demande = session_model.objects.filter(pk=session_id).first()
    if demande is None:
        return True
    return not demande.est_active()


class CookieJWTAuthentication(BaseAuthentication):
    """
    Lit le JWT depuis le cookie httpOnly 'access_token'.
    Fallback sur l'en-tete Authorization: Bearer pour la compatibilite
    avec les clients qui n'utilisent pas les cookies (ex: scripts, tests).
    """

    def authenticate(self, request):
        # 1. Cookie httpOnly (prioritaire — inaccessible au JavaScript)
        token = request.COOKIES.get('access_token')

        # 2. Fallback Bearer token (backward compat)
        if not token:
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]

        if not token:
            return None

        try:
            validated = AccessToken(token)
        except (TokenError, InvalidToken):
            raise AuthenticationFailed('Token invalide ou expire.')

        User = get_user_model()
        try:
            user = User.objects.select_related('company', 'role').get(
                pk=validated['user_id']
            )
        except User.DoesNotExist:
            raise AuthenticationFailed('Utilisateur introuvable.')

        if not user.is_active:
            raise AuthenticationFailed('Compte desactive.')

        # AUD408 — révocation EFFECTIVE du jeton d'accès. Jusqu'ici logout,
        # révocation d'une session distante, éviction concurrente et changement
        # de mot de passe ne blacklistaient que le REFRESH : le jeton d'accès
        # déjà émis continuait d'authentifier jusqu'à 30 min après une
        # révocation pourtant affichée comme effective — y compris pour un
        # appareil distant qui ne reçoit littéralement aucune réponse. On
        # consulte l'état de la session portée par le claim ``sid``.
        from .session_policy import access_session_revoked
        if access_session_revoked(validated):
            raise AuthenticationFailed(
                'Session révoquée. Reconnectez-vous.')

        # AUD404 — coupe-circuit RÉEL des sessions d'impersonation (NTADM22).
        # `terminer()` ne posait que `terminee_le` en base : le jeton d'accès
        # déjà émis pour le support restait valable jusqu'à 30 min, avec accès
        # complet à toute la société, alors que le bandeau affichait « session
        # terminée ». Le lookup existait depuis toujours dans
        # `impersonation_service.session_depuis_requete()`, mais SEULEMENT pour
        # l'audit et l'affichage — jamais comme garde d'authentification.
        # Ne coûte une requête que pour un jeton PORTANT le claim (jamais sur le
        # chemin d'un utilisateur ordinaire).
        if _impersonation_revoquee(validated):
            raise AuthenticationFailed(
                "Session d'assistance terminée ou expirée.")

        # XPLT19 — société ACTIVE : si le jeton porte un claim
        # ``active_company_id`` et que l'utilisateur est bien membre de cette
        # société, on borne CETTE requête à la société choisie en posant
        # ``user.company`` sur l'instance fraîche de la requête (jamais un
        # ``save()`` : le FK d'attache n'est pas modifié). Sans claim ou pour un
        # compte mono-société, ``user.company`` reste sa société d'attache —
        # comportement byte-identique. Toute revendication non autorisée est
        # ignorée (repli sur la société d'attache) : aucune fuite cross-société.
        from authentication.active_company import (
            ACTIVE_COMPANY_CLAIM, resolve_active_company,
            set_active_company_id,
        )
        claimed = None
        try:
            claimed = validated.get(ACTIVE_COMPANY_CLAIM)
        except Exception:  # noqa: BLE001 — jeton sans le claim (legacy/for_user)
            claimed = None
        if claimed is not None and claimed != user.company_id:
            active = resolve_active_company(user, claimed)
            if active is not None:
                user.company = active
        set_active_company_id(user.company_id)

        # SCA18 — statut tenant appliqué ICI (et non dans un middleware) : la
        # société est déjà jointe (select_related) donc le contrôle coûte ZÉRO
        # requête, là où un middleware devait ré-authentifier (double SELECT
        # utilisateur par requête — le budget YOPSB13 l'a attrapé). On borne
        # la société EFFECTIVE (post-switch XPLT19) ; superuser exempté ; les
        # chemins /auth/ et /token/ restent joignables (cycle de vie du jeton
        # — le refresh porte sa propre garde SCA18 côté vue).
        from rest_framework.exceptions import PermissionDenied
        path = getattr(request, 'path', '') or ''
        exempt = path.startswith(('/api/django/auth/', '/api/django/token/'))
        company = getattr(user, 'company', None)
        if (company is not None and not exempt
                and not user.is_superuser
                and not getattr(company, 'est_operationnel', True)):
            raise PermissionDenied(
                "Ce compte société est suspendu. "
                "L'accès est temporairement bloqué.")

        return (user, validated)

    def authenticate_header(self, request):
        return 'Bearer realm="api"'


class CookieJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """YAPIC6 — décrit `CookieJWTAuthentication` dans le schéma OpenAPI.

    Sans cette extension, drf-spectacular émettait « could not resolve
    authenticator » sur CHAQUE vue (1244 avertissements uniques, ~66 % du
    bruit du schéma) et le document ne portait AUCUN `securitySchemes` — donc
    ni Swagger ni un client généré ne savaient comment s'authentifier.

    Elle est définie ici (et non dans un module `schema.py` séparé) parce que
    drf-spectacular n'enregistre une extension que si son module est importé :
    la poser à côté de la classe cible garantit l'enregistrement dès que
    l'authenticator lui-même est chargé.
    """

    target_class = 'authentication.cookie_auth.CookieJWTAuthentication'
    name = 'cookieJWT'

    def get_security_definition(self, auto_schema):
        # Le porteur PRIMAIRE est le cookie httpOnly `access_token` ; le repli
        # `Authorization: Bearer <jwt>` reste accepté par `authenticate()`
        # (compat scripts/tests) et est décrit dans la description.
        return {
            'type': 'apiKey',
            'in': 'cookie',
            'name': 'access_token',
            'description': (
                "JWT d'accès porté par le cookie httpOnly `access_token`. "
                "Repli accepté : en-tête `Authorization: Bearer <jwt>`."
            ),
        }
