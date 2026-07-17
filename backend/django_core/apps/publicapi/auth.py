"""Authentification, permissions et throttling de l'API publique (N89).

L'API publique n'utilise PAS la session/JWT : elle s'authentifie par clé d'API
portée dans l'en-tête « Authorization: Api-Key <clé> ». La clé appartient à une
société ; toute requête authentifiée par clé est donc scopée à CETTE société,
côté serveur, jamais depuis le corps de la requête.
"""
from django.utils import timezone

from rest_framework import authentication, exceptions, permissions
from rest_framework.throttling import SimpleRateThrottle

from .models import ApiKey, hash_key

AUTH_KEYWORD = 'Api-Key'


class ApiKeyUser:
    """Acteur léger anonyme représentant une clé d'API.

    DRF exige un objet `request.user` ; on n'a pas d'utilisateur connecté, donc
    on expose un porteur minimal non authentifié au sens session. La société et
    les scopes sont portés par `request.auth` (l'instance ApiKey).
    """
    is_authenticated = False  # pas un utilisateur de session
    is_anonymous = True

    def __init__(self, api_key):
        self.api_key = api_key
        self.company = api_key.company
        self.company_id = api_key.company_id

    def __str__(self):
        return f'ApiKey<{self.api_key.prefix}…>'


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Lit « Authorization: Api-Key <clé> », résout la société, pose le scope.

    Renvoie (ApiKeyUser, ApiKey) ; `request.auth` est l'instance ApiKey, qui
    porte company + scopes. Rejette une clé absente du système ou désactivée.
    """

    keyword = AUTH_KEYWORD

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode('latin-1')
        if not header:
            return None  # laisse les autres classes / l'anonyme jouer
        parts = header.split()
        if parts[0].lower() != self.keyword.lower():
            return None  # autre schéma (Bearer…) — pas pour nous
        if len(parts) == 1:
            raise exceptions.AuthenticationFailed('Clé API manquante.')
        if len(parts) > 2:
            raise exceptions.AuthenticationFailed('En-tête Api-Key invalide.')

        raw_key = parts[1]
        try:
            api_key = ApiKey.objects.select_related('company').get(
                key_hash=hash_key(raw_key))
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed('Clé API invalide.')
        if not api_key.enabled:
            raise exceptions.AuthenticationFailed('Clé API désactivée.')
        # NTAPI23 — la grace period de rotation est TERMINÉE : une clé
        # au-delà de `expire_le` est rejetée comme n'importe quelle clé
        # désactivée (la nouvelle clé émise par `rotate()` continue de
        # fonctionner sans interruption).
        if api_key.est_expiree:
            raise exceptions.AuthenticationFailed(
                'Clé API expirée (période de grâce de rotation terminée).')

        # Trace d'usage (best-effort, non bloquant).
        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        return (ApiKeyUser(api_key), api_key)

    def authenticate_header(self, request):
        return self.keyword


class HasApiScope(permissions.BasePermission):
    """Exige que la clé porte le scope déclaré sur la vue (`required_scope`)."""

    message = 'Cette clé API n’a pas le droit nécessaire.'

    def has_permission(self, request, view):
        api_key = getattr(request, 'auth', None)
        if not isinstance(api_key, ApiKey):
            return False
        required = getattr(view, 'required_scope', None)
        if not required:
            return False
        return api_key.has_scope(required)


class ApiKeyRateThrottle(SimpleRateThrottle):
    """Limite le débit par CLÉ d'API (pas par IP).

    Sans clé reconnue, on ne throttle pas ici (la requête sera de toute façon
    rejetée par l'auth/permission). Taux configurable via le scope « publicapi ».
    """
    scope = 'publicapi'

    def get_cache_key(self, request, view):
        api_key = getattr(request, 'auth', None)
        if not isinstance(api_key, ApiKey):
            return None  # non throttlé ici
        return self.cache_format % {'scope': self.scope, 'ident': api_key.pk}
