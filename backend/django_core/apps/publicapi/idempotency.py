"""XPLT5 — idempotence des ÉCRITURES de l'API publique (`Idempotency-Key`).

Scope : (clé API, endpoint, `Idempotency-Key`). Rejouer le même triplet avec un
corps IDENTIQUE renvoie la réponse mémorisée (aucune nouvelle création) ; avec
un corps DIFFÉRENT → 409. Sans en-tête, comportement normal inchangé (toujours
une nouvelle écriture). Distinct du futur mixin générique `core` (YAPIC9) qui
couvrira les POST internes JWT — celui-ci ne couvre que l'API publique par clé.
"""
import hashlib
import json

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

from .models import IdempotencyRecord

IDEMPOTENCY_HEADER = 'HTTP_IDEMPOTENCY_KEY'

#: AANA34 — longueur maximale d'une `Idempotency-Key` : celle de la colonne
#: qui la mémorise (lue sur le modèle, jamais recopiée).
LONGUEUR_MAX_CLE = IdempotencyRecord._meta.get_field(
    'idempotency_key').max_length

#: AANA34 — statut d'une clé RÉSERVÉE dont l'action n'est pas encore jouée
#: (n'est jamais visible hors de la transaction qui l'a posée).
STATUT_RESERVE = 0


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


def valider_cle(idem_key):
    """AANA34 — 400 AVANT toute écriture pour une clé trop longue (elle
    faisait écrire l'objet PUIS échouer la mémorisation en 500)."""
    if idem_key and len(idem_key) > LONGUEUR_MAX_CLE:
        raise ValidationError({'Idempotency-Key': (
            f"« Idempotency-Key » trop longue : {LONGUEUR_MAX_CLE} "
            "caractères au maximum.")})


def executer_idempotent(*, company, api_key, endpoint, idem_key, body,
                        perform):
    """Joue ``perform()`` (qui renvoie un ``Response``) au plus UNE fois par
    triplet (clé API, endpoint, `Idempotency-Key`).

    AANA34 — la clé est RÉSERVÉE (insertion sous contrainte d'unicité, dans
    la même transaction que l'action) AVANT l'action : une seconde requête
    concurrente portant la même clé attend la fin de la première, puis
    rejoue sa réponse mémorisée — jamais un second objet. Une action qui
    échoue (exception) annule la réservation avec elle. Un rejeu au corps
    différent ⇒ 409. Sans en-tête : ``perform()`` tel quel.
    """
    valider_cle(idem_key)
    if not idem_key:
        return perform()
    fingerprint = _fingerprint(body)
    with transaction.atomic():
        try:
            with transaction.atomic():
                record = IdempotencyRecord.objects.create(
                    company=company, api_key=api_key, endpoint=endpoint,
                    idempotency_key=idem_key,
                    request_fingerprint=fingerprint,
                    response_status=STATUT_RESERVE, response_body={})
        except IntegrityError:
            record = None
        if record is None:
            existant = IdempotencyRecord.objects.select_for_update().get(
                api_key=api_key, endpoint=endpoint, idempotency_key=idem_key)
            if existant.request_fingerprint != fingerprint:
                raise IdempotencyConflict()
            return Response(existant.response_body,
                            status=existant.response_status)
        response = perform()
        record.response_status = response.status_code
        record.response_body = response.data
        record.save(update_fields=['response_status', 'response_body'])
        return response
