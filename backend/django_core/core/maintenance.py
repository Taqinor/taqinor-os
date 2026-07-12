"""NTPLT55 — Middleware du mode lecture seule (maintenance).

Quand ``core.MaintenanceMode`` est actif (singleton DB, cache 5 s), toute
requête à MÉTHODE NON-SÛRE (POST/PUT/PATCH/DELETE) reçoit un 503 JSON français
+ ``Retry-After`` — sauf une ALLOWLIST (login/logout/health) pour qu'un admin
puisse se connecter et désactiver le mode. Les lectures (GET/HEAD/OPTIONS)
passent toujours : l'ERP reste consultable pendant une bascule de schéma.

Activer ce middleware : l'ajouter à ``MIDDLEWARE`` dans les settings (étape de
wiring hors ``core``). Sans cela, le modèle existe mais n'a aucun effet.
"""
from __future__ import annotations

from django.http import JsonResponse

# Méthodes considérées comme SÛRES (jamais bloquées en maintenance).
_SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

# Fragments de chemin toujours autorisés (l'admin doit pouvoir se connecter et
# lever la maintenance ; les sondes de santé doivent répondre).
_ALLOW_SUBSTRINGS = (
    '/auth/login', '/auth/logout', '/auth/token', '/health/',
    # L'endpoint de bascule lui-même, pour désactiver la maintenance.
    '/core/maintenance',
)

# Délai suggéré au client avant re-tentative (secondes).
_RETRY_AFTER = 30


class MaintenanceModeMiddleware:
    """Répond 503 aux écritures pendant la maintenance ; laisse lire."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in _SAFE_METHODS and self._is_blocked(request):
            return self._maintenance_response()
        return self.get_response(request)

    @staticmethod
    def _path_allowed(path: str) -> bool:
        return any(sub in path for sub in _ALLOW_SUBSTRINGS)

    def _is_blocked(self, request) -> bool:
        if self._path_allowed(request.path):
            return False
        from .models import MaintenanceMode
        return MaintenanceMode.is_active()

    @staticmethod
    def _maintenance_response():
        from .models import MaintenanceMode
        try:
            message = MaintenanceMode.get_solo().message
        except Exception:  # noqa: BLE001 — DB KO → message générique
            message = 'Maintenance en cours.'
        resp = JsonResponse(
            {'detail': message, 'maintenance': True}, status=503)
        resp['Retry-After'] = str(_RETRY_AFTER)
        return resp
