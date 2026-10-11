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


# ENF1b — préfixes de l'API interne (le miroir `api/v1/` sert les mêmes vues).
# `/api/public/` a SA propre enveloppe d'erreur (apps.publicapi) : hors champ.
_PREFIXES_API_INTERNE = ('/api/django/', '/api/v1/')


class ApiJson404Middleware:
    """ENF1b — une URL d'API interne qui ne correspond à AUCUNE route répond
    404 avec l'enveloppe JSON ``ErreurApi``, jamais la page HTML de Django.

    Constat (api-fuzz du 09/10) : 510 des 533 « Undocumented Content-Type »
    étaient la page « Page not found » HTML (technique en DEBUG, générique
    sinon) servie quand l'identifiant de chemin ne passe pas le motif du
    routeur (``…/devis/0.5/``, ``…/entries/.%C3%98c/``) : la résolution
    d'URL échoue AVANT toute vue DRF, donc avant
    ``core.exceptions.taqinor_exception_handler``. Seules les réponses 404
    HTML SANS route résolue (``request.resolver_match`` absent) sont
    réécrites : une vue qui sert elle-même un 404 (HTML ou non) est
    intouchée, le statut ne change jamais.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (response.status_code == 404
                and request.path.startswith(_PREFIXES_API_INTERNE)
                and getattr(request, 'resolver_match', None) is None
                and response.get('Content-Type', '').startswith('text/html')):
            from django.http import JsonResponse

            from core.exceptions import MESSAGE_NOT_FOUND
            request_id = getattr(request, 'request_id', None)
            nouvelle = JsonResponse({
                'detail': MESSAGE_NOT_FOUND,
                'error': {
                    'code': 'not_found',
                    'message': MESSAGE_NOT_FOUND,
                    'fields': None,
                    'request_id': request_id,
                },
            }, status=404)
            if request_id:
                nouvelle['X-Request-Id'] = request_id
            return nouvelle
        return response
