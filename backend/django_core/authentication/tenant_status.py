"""SCA18 — Enforcement du statut du tenant sur l'API.

``TenantStatusMiddleware`` renvoie **403** (message français) sur les appels API
d'un tenant NON actif (``Company.statut`` ∈ {suspendu, en fermeture}). Cela
double la garde du login (qui refuse déjà d'émettre un JWT) : un jeton déjà émis
avant la suspension est ainsi rejeté à chaque requête ET au refresh.

Invariants (frontières intactes) :

* **Défaut = actif** : sans société suspendue, comportement BYTE-IDENTIQUE
  (aucun 403 nouveau). Un tenant ``est_operationnel`` passe toujours.
* **Superuser exempté** : le support/console fondateur (superuser) n'est jamais
  bloqué — il doit pouvoir réactiver un tenant suspendu.
* **Endpoints exemptés** : ``/auth/…`` (logout, refresh d'un compte pour lire son
  état, switch), la console staff (``/api/django/auth/console/…``) et les
  surfaces publiques tokenisées ne sont jamais bloqués — sinon un tenant
  suspendu ne pourrait même pas se déconnecter proprement.
* **Multi-tenant** : seule la société suspendue voit le 403 ; les autres ne sont
  pas affectées.

Placé APRÈS l'authentification Django ; résout le JWT DRF best-effort (aucun
blocage sans jeton valide), même patron que ``core.permissions.
DisabledModuleMiddleware``.
"""
from __future__ import annotations

from django.http import JsonResponse

_API_ROOT = 'api/django/'

# Préfixes (2ᵉ segment de /api/django/<seg>/) TOUJOURS exemptés : un tenant
# suspendu doit pouvoir se déconnecter / lire /auth/me/ (pour afficher le
# message), et la console staff pilote justement la réactivation.
_EXEMPT_PREFIXES = frozenset({
    '', 'auth', 'token', 'admin', 'public', 'static',
})


def _is_exempt_path(path):
    """True si ``path`` n'est jamais soumis à la garde de statut tenant."""
    p = path.lstrip('/')
    if not p.startswith(_API_ROOT):
        # Hors de l'API Django (admin Django, statiques…) : jamais bloqué ici.
        return True
    reste = p[len(_API_ROOT):]
    segment = reste.split('/', 1)[0]
    return segment in _EXEMPT_PREFIXES


class TenantStatusMiddleware:
    """Renvoie 403 sur les appels API d'un tenant non actif (SCA18)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def _company(self, request):
        """Résout la société de l'appelant, best-effort (jamais d'exception)."""
        user = getattr(request, 'user', None)
        company = getattr(user, 'company', None)
        if company is not None:
            return user, company
        try:
            from authentication.cookie_auth import CookieJWTAuthentication
            result = CookieJWTAuthentication().authenticate(request)
        except Exception:  # noqa: BLE001 — jeton invalide ⇒ pas de blocage
            return None, None
        if result is None:
            return None, None
        u = result[0]
        return u, getattr(u, 'company', None)

    def __call__(self, request):
        if not _is_exempt_path(request.path):
            user, company = self._company(request)
            if (company is not None
                    and not getattr(user, 'is_superuser', False)
                    and not getattr(company, 'est_operationnel', True)):
                return JsonResponse(
                    {'detail': "Ce compte société est suspendu. "
                               "L'accès est temporairement bloqué."},
                    status=403)
        return self.get_response(request)
