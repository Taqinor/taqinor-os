"""YAPIC3 — enveloppe d'erreur DRF unifiée via un `EXCEPTION_HANDLER` global.

Sans ceci, les 400 (dict field-keyed DRF natif), 401/403 (``{"detail": …}``),
404 et 500 ont des formes DIFFÉRENTES et aucun code machine stable n'existe
pour qu'un client (frontend, intégration) distingue les cas sans parser un
message humain. ``taqinor_exception_handler`` délègue D'ABORD au handler DRF
natif (jamais de logique de statut HTTP dupliquée) PUIS reformate la réponse
dans une forme UNIQUE :

    {"error": {"code": "<slug stable>", "message": "<humain FR>",
               "fields": {<champ>: [<msgs>]}, "request_id": "<id>"}}

``code`` est dérivé de la classe d'exception (jamais du message, qui peut
changer) ; ``fields`` n'apparaît QUE pour les 400 de validation (dict
field-keyed). ``request_id`` est lu depuis ``request.request_id`` (posé par
``core.middleware.RequestIdMiddleware``, YAPIC4) — ``None`` tant que ce
middleware n'est pas monté, jamais une erreur.

Une exception NON gérée par DRF (``exception_handler`` renvoie ``None``) est
elle aussi enveloppée ici en 500 ``server_error`` — le SEUL endroit qui
transforme une exception Python arbitraire en JSON, pour que 100% des
réponses d'erreur DRF (y compris les crashs) portent la même forme.
"""
from __future__ import annotations

from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# Slug stable par classe d'exception DRF — jamais dérivé du message humain
# (qui peut être traduit/reformulé sans casser un client qui teste `code`).
_CODE_BY_EXCEPTION = (
    (drf_exceptions.ValidationError, 'validation_error'),
    (drf_exceptions.AuthenticationFailed, 'not_authenticated'),
    (drf_exceptions.NotAuthenticated, 'not_authenticated'),
    (drf_exceptions.PermissionDenied, 'permission_denied'),
    (drf_exceptions.NotFound, 'not_found'),
    (drf_exceptions.Throttled, 'throttled'),
    (drf_exceptions.MethodNotAllowed, 'method_not_allowed'),
    (drf_exceptions.NotAcceptable, 'not_acceptable'),
    (drf_exceptions.UnsupportedMediaType, 'unsupported_media_type'),
    (drf_exceptions.ParseError, 'parse_error'),
)


def _code_for(exc) -> str:
    for exc_class, code in _CODE_BY_EXCEPTION:
        if isinstance(exc, exc_class):
            return code
    if isinstance(exc, drf_exceptions.APIException):
        return 'api_error'
    return 'server_error'


def _message_for(exc, code: str) -> str:
    """Message humain FR — stable et générique par code (jamais le détail
    brut DRF, qui peut fuiter des informations internes sur un 500)."""
    if code == 'server_error':
        return "Une erreur inattendue s'est produite."
    detail = getattr(exc, 'detail', None)
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return str(detail[0])
    if isinstance(detail, dict):
        # Vue générale — le détail par champ va dans `fields`, pas ici.
        non_field = detail.get('non_field_errors') or detail.get('detail')
        if non_field:
            return str(non_field[0] if isinstance(non_field, list) else non_field)
    return str(exc)


def _fields_for(exc, code: str):
    """`fields` UNIQUEMENT pour les 400 de validation avec un detail
    field-keyed (dict) — jamais pour les autres codes."""
    if code != 'validation_error':
        return None
    detail = getattr(exc, 'detail', None)
    if not isinstance(detail, dict):
        return None
    fields = {}
    for key, value in detail.items():
        if key == 'non_field_errors':
            continue
        fields[key] = value if isinstance(value, list) else [value]
    return fields or None


def _request_id(context) -> str | None:
    request = context.get('request') if context else None
    return getattr(request, 'request_id', None) if request is not None else None


def _rate_limit_headers_for(exc, context):
    """YAPIC12 — X-RateLimit-Limit/X-RateLimit-Remaining sur un 429. Ne
    RE-DÉCLENCHE jamais ``allow_request`` (mutation de l'état du throttle,
    ex. compteur cache) : lecture STATIQUE de la config de débit du premier
    throttle scopé de la vue seulement — best-effort, jamais bloquant."""
    if not isinstance(exc, drf_exceptions.Throttled):
        return {}
    view = context.get('view') if context else None
    if view is None or not hasattr(view, 'get_throttles'):
        return {}
    try:
        for throttle in view.get_throttles():
            rate = getattr(throttle, 'rate', None) or (
                throttle.get_rate() if hasattr(throttle, 'get_rate') else None)
            if not rate:
                continue
            num_requests, _duration = throttle.parse_rate(rate)
            return {
                'X-RateLimit-Limit': str(num_requests),
                'X-RateLimit-Remaining': '0',
            }
    except Exception:  # noqa: BLE001 — advisory headers, never break the 429
        pass
    return {}


def taqinor_exception_handler(exc, context):
    """`REST_FRAMEWORK['EXCEPTION_HANDLER']` — enveloppe UNIQUE pour toute
    réponse d'erreur DRF, y compris les exceptions non reconnues par DRF
    (repliées en 500 `server_error`)."""
    response = drf_exception_handler(exc, context)
    request_id = _request_id(context)

    if response is None:
        # Exception non gérée par DRF (ex. bug applicatif) — la forme
        # unifiée reste due même ici ; le statut HTTP/sémantique tenant ne
        # change JAMAIS (toujours 500, jamais masqué en 200).
        code = 'server_error'
        body = {
            'error': {
                'code': code,
                'message': _message_for(exc, code),
                'fields': None,
                'request_id': request_id,
            },
        }
        return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    code = _code_for(exc)
    envelope = {
        'code': code,
        'message': _message_for(exc, code),
        'fields': _fields_for(exc, code),
        'request_id': request_id,
    }
    # YAPIC3 — enveloppe ADDITIVE, jamais un remplacement de corps. On CONSERVE
    # la forme DRF native au niveau racine (dict field-keyed pour un 400,
    # ``{"detail": …}`` pour 401/403/404) — sinon on casse TOUT consommateur
    # existant (frontend + ~centaines de tests) qui lit ``resp.data['<champ>']``
    # ou ``resp.data['detail']`` — et on expose EN PLUS l'enveloppe machine
    # stable sous la clé ``error`` (code/message/fields/request_id). Un champ de
    # validation littéralement nommé ``error`` (rarissime) est préservé tel quel.
    if isinstance(response.data, dict):
        response.data.setdefault('error', envelope)
    # Corps non-dict (rare) : laissé intact pour la rétro-compatibilité ; le
    # request_id reste disponible via l'en-tête X-Request-Id (YAPIC4).
    for header, value in _rate_limit_headers_for(exc, context).items():
        response[header] = value
    return response
