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
