"""YAPIC4 — middleware d'identifiant de corrélation (`X-Request-Id`) sur
100% des réponses (foundation).

``RequestIdMiddleware`` est l'unique AUTORITÉ sur ``request.request_id`` :
lit un ``X-Request-Id`` entrant s'il est présent ET valide (chaîne non vide,
imprimable, ≤ 200 caractères — sinon traité comme absent, jamais un rejet de
requête), sinon génère un ``uuid4``. Posé sur ``request.request_id`` (lu
ensuite par ``core.exceptions.taqinor_exception_handler`` pour remplir
``error.request_id``, YAPIC3) et échoé dans l'en-tête ``X-Request-Id`` de
CHAQUE réponse — succès ET erreur.

Placé EN PREMIER dans ``MIDDLEWARE`` (avant tout autre middleware) pour que
``request.request_id`` soit disponible à TOUTE la suite de la requête,
y compris ``core.observability.RequestObservabilityMiddleware`` (NTPLT43),
qui RÉUTILISE désormais cet id au lieu d'en dériver un second (évite deux
identifiants divergents sur la même requête — voir sa docstring)."""
from __future__ import annotations

import uuid


def _is_valid_incoming_id(raw: str) -> bool:
    if not raw:
        return False
    if len(raw) > 200:
        return False
    return raw.isprintable()


class RequestIdMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get('HTTP_X_REQUEST_ID', '').strip()
        request_id = incoming if _is_valid_incoming_id(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        response = self.get_response(request)
        response['X-Request-Id'] = request_id
        return response
