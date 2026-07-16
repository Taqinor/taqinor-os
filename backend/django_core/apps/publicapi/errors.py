"""NTAPI3 — enveloppe d'erreur normalisée DÉDIÉE à l'API publique (/api/public/).

Handler d'exception DRF façon Stripe, DISTINCT du handler global
``core.exceptions.taqinor_exception_handler`` (YAPIC3, qui reste inchangé pour
``/api/django/``, ``/api/v1/``…). Toute réponse d'erreur de l'API publique
devient INTÉGRALEMENT :

    {"error": {"type": "...", "code": "...", "message": "...",
               "param": "..."|null, "doc_url": "...", "request_id": "..."}}

``type`` catégorise l'erreur (``invalid_request_error`` / ``authentication_error``
/ ``rate_limit_error`` / ``api_error``) façon Stripe ; ``code`` est un slug
stable dérivé de la CLASSE d'exception (jamais du message, qui peut changer/être
traduit) ; ``param`` porte le premier champ fautif pour un 400 de validation ;
``doc_url`` pointe vers l'ancre du catalogue d'erreurs consultable (NTAPI4,
``/api/public/v1/errors/``) ; ``request_id`` est lu depuis ``request.request_id``
(posé par ``core.middleware.RequestIdMiddleware``, YAPIC4 — déjà monté
globalement, donc déjà présent ici aussi).

Contrairement à YAPIC3 (additif, préserve la forme DRF native pour ne rien
casser des consommateurs internes existants), ce contrat est NEUF pour l'API
publique : le corps Stripe-like est la SEULE forme renvoyée.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

# Slug stable par classe d'exception DRF connue — jamais dérivé du message.
_KNOWN_CODES = (
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
# ``type`` Stripe-like forcé pour certains codes (le reste dérive du statut
# HTTP — cf. `_type_for`), pour couvrir aussi les `APIException` custom de
# l'app (ex. `IdempotencyConflict`, code `idempotency_conflict`, statut 409).
_TYPE_OVERRIDES = {
    'not_authenticated': 'authentication_error',
    'permission_denied': 'authentication_error',
    'throttled': 'rate_limit_error',
}


def _code_for(exc) -> str:
    # DRF traduit `Http404` / `PermissionDenied` Django en réponses 404/403 mais
    # passe l'exception Django BRUTE à ce handler (jamais la classe DRF) — il
    # faut donc les reconnaître ici, sinon un 404 légitime retombe en
    # `server_error` alors que le statut HTTP est bien 404 (bug NTAPI3).
    if isinstance(exc, Http404):
        return 'not_found'
    if isinstance(exc, DjangoPermissionDenied):
        return 'permission_denied'
    for exc_class, code in _KNOWN_CODES:
        if isinstance(exc, exc_class):
            return code
    if isinstance(exc, drf_exceptions.APIException):
        # Sous-classe custom (ex. `IdempotencyConflict.default_code =
        # 'idempotency_conflict'`) : réutilisée telle quelle. `'error'` est le
        # défaut générique de `APIException` — pas un slug utile.
        custom = getattr(exc, 'default_code', None)
        if custom and custom != 'error':
            return custom
        return 'api_error'
    return 'server_error'


def _message_for(exc, code: str) -> str:
    if code == 'server_error':
        return "Une erreur inattendue s'est produite."
    detail = getattr(exc, 'detail', None)
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return str(detail[0])
    if isinstance(detail, dict):
        non_field = detail.get('non_field_errors') or detail.get('detail')
        if non_field:
            return str(non_field[0] if isinstance(non_field, list) else non_field)
        for value in detail.values():
            return str(value[0] if isinstance(value, list) else value)
    return str(exc)


def _param_for(exc, code: str):
    """Premier champ fautif d'un 400 de validation (dict field-keyed) —
    ``None`` pour tout autre code (jamais de fuite de structure interne)."""
    if code != 'validation_error':
        return None
    detail = getattr(exc, 'detail', None)
    if not isinstance(detail, dict):
        return None
    for key in detail:
        if key != 'non_field_errors':
            return key
    return None


def _type_for(code: str, status_code) -> str:
    if code in _TYPE_OVERRIDES:
        return _TYPE_OVERRIDES[code]
    if status_code and status_code >= 500:
        return 'api_error'
    return 'invalid_request_error'


def _doc_url(code: str) -> str:
    # NTAPI4 (catalogue d'erreurs consultable) exposera `/api/public/v1/errors/`
    # — l'ancre stable par code est déjà utilisable en avance de phase.
    return f'/api/public/v1/errors/#{code}'


def _request_id(context):
    request = context.get('request') if context else None
    return getattr(request, 'request_id', None) if request is not None else None


def public_api_exception_handler(exc, context):
    """``get_exception_handler()`` DÉDIÉ aux vues de l'API publique.

    Délègue D'ABORD au handler DRF natif (jamais de logique de statut HTTP
    dupliquée), puis REMPLACE intégralement le corps par l'enveloppe
    Stripe-like ci-dessus. Une exception NON reconnue par DRF (handler natif
    renvoyant ``None``) est elle aussi enveloppée, en 500 ``server_error``.
    """
    response = drf_exception_handler(exc, context)
    request_id = _request_id(context)

    if response is None:
        code = 'server_error'
        body = {'error': {
            'type': 'api_error',
            'code': code,
            'message': _message_for(exc, code),
            'param': None,
            'doc_url': _doc_url(code),
            'request_id': request_id,
        }}
        return Response(body, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    code = _code_for(exc)
    envelope = {
        'type': _type_for(code, response.status_code),
        'code': code,
        'message': _message_for(exc, code),
        'param': _param_for(exc, code),
        'doc_url': _doc_url(code),
        'request_id': request_id,
    }
    # Contrat Stripe-like : le corps devient CE dict, pas une fusion (contrat
    # NEUF pour l'API publique — pas de consommateur existant à préserver).
    response.data = {'error': envelope}
    return response
