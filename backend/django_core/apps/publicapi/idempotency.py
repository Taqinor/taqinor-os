"""XPLT5 — idempotence des ÉCRITURES de l'API publique (`Idempotency-Key`).

Scope : (clé API, endpoint, `Idempotency-Key`). Rejouer le même triplet avec un
corps IDENTIQUE renvoie la réponse mémorisée (aucune nouvelle création) ; avec
un corps DIFFÉRENT → 409. Sans en-tête, comportement normal inchangé (toujours
une nouvelle écriture). Distinct du futur mixin générique `core` (YAPIC9) qui
couvrira les POST internes JWT — celui-ci ne couvre que l'API publique par clé.
"""
import hashlib
import json

from rest_framework import status
from rest_framework.exceptions import APIException

from .models import IdempotencyRecord

IDEMPOTENCY_HEADER = 'HTTP_IDEMPOTENCY_KEY'


class IdempotencyConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "Cette « Idempotency-Key » a déjà été utilisée avec un corps de "
        "requête différent."
    )
    default_code = 'idempotency_conflict'


def _fingerprint(body):
    canonical = json.dumps(body, default=str, sort_keys=True).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def get_idempotency_key(request):
    """Lit l'en-tête `Idempotency-Key` (absent → None, comportement normal)."""
    raw = request.META.get(IDEMPOTENCY_HEADER) or request.headers.get(
        'Idempotency-Key')
    return raw.strip() if raw else None


def replay_or_none(*, api_key, endpoint, idem_key, body):
    """Renvoie (status, response_body) mémorisés si CE triplet a déjà été vu
    avec un corps identique. Lève 409 si le corps diverge. Renvoie None si la
    clé d'idempotence est neuve (l'appelant doit alors écrire normalement puis
    appeler `remember`)."""
    if not idem_key:
        return None
    fingerprint = _fingerprint(body)
    try:
        record = IdempotencyRecord.objects.get(
            api_key=api_key, endpoint=endpoint, idempotency_key=idem_key)
    except IdempotencyRecord.DoesNotExist:
        return None
    if record.request_fingerprint != fingerprint:
        raise IdempotencyConflict()
    return record.response_status, record.response_body


def remember(*, company, api_key, endpoint, idem_key, body, response_status,
             response_body):
    """Mémorise la réponse pour ce triplet (no-op si pas d'en-tête fourni)."""
    if not idem_key:
        return
    IdempotencyRecord.objects.get_or_create(
        api_key=api_key, endpoint=endpoint, idempotency_key=idem_key,
        defaults={
            'company': company,
            'request_fingerprint': _fingerprint(body),
            'response_status': response_status,
            'response_body': response_body,
        },
    )
