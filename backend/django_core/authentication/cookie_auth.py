"""
Authentification JWT via httpOnly cookie.
Remplace la lecture du token dans l'en-tete Authorization.
"""
from django.contrib.auth import get_user_model
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

        return (user, validated)

    def authenticate_header(self, request):
        return 'Bearer realm="api"'
