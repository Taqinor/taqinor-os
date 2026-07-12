"""YDATA12 + YAPIC9 — idempotence, DEUX mécanismes DISTINCTS dans ce même
module fondation :

  * ``ProcessedWebhookEvent``/``dedupe_event`` (YDATA12) — webhooks ENTRANTS
    (ex. ``apps/crm/webhooks.py``) : insertion AVANT tout effet, DANS une
    transaction, contrainte unique ``(company, source, event_id)``.
  * ``IdempotencyRecord``/``IdempotentCreateMixin`` (YAPIC9) — POST INTERNES
    de l'ERP authentifiés JWT (créer devis/facture/BC/ticket…) : REJOUE la
    réponse mémorisée pour un ``Idempotency-Key`` déjà vu avec un corps
    IDENTIQUE ; 409 si le corps DIFFÈRE ; sans en-tête, comportement inchangé.

Distincts de deux mécanismes voisins déjà dans le repo (jamais réécrits ici) :
  * ``core/webhooks.py`` — dispatch SORTANT de webhooks signés (existant).
  * ``core.ProcessedEvent`` (``core/models.py``, NTPLT9/10) — dédup du
    CONSOMMATEUR du bus d'événements interne (``event_id`` + ``handler_name``,
    sans FK company) : périmètre différent de ``ProcessedWebhookEvent``.
  * ``apps/publicapi/idempotency.py`` (XPLT5) — idempotence des ÉCRITURES de
    l'API PUBLIQUE PAR CLÉ API (``Idempotency-Key`` scopé par ``ApiKey``).
    ``core.IdempotencyRecord`` ci-dessous est le pendant pour les POST
    INTERNES JWT — un seul modèle d'idempotence PAR périmètre dans tout le
    repo, jamais un second dans publicapi pour ce cas.

``dedupe_event`` insère la ligne (contrainte unique
``(company, source, event_id)``) DANS une transaction, AVANT tout effet de
bord : la 2ᵉ arrivée concurrente lève IntegrityError → l'appelant répond
"déjà traité" (200) sans rejouer l'effet, au lieu du pattern
lecture-puis-décision (race condition classique).
"""
from __future__ import annotations

import hashlib
import json

from django.db import IntegrityError, models, transaction
from rest_framework import status
from rest_framework.exceptions import APIException


class ProcessedWebhookEvent(models.Model):
    """Marque un événement webhook ENTRANT comme traité — une seule fois
    par ``(company, source, event_id)``.

    Champs déclarés directement (plutôt qu'hériter ``core.models.TenantModel``,
    ARC1) : ``core/models.py`` réexportera CE modèle en bas de fichier pour la
    découverte Django (même pattern que ``apps/installations/models.py`` avec
    ses fichiers ``models_*`` éclatés) — hériter ``TenantModel`` depuis ici
    créerait un import circulaire (``core.models`` importerait
    ``core.idempotency`` qui importerait ``core.models``)."""

    company = models.ForeignKey(
        'authentication.Company',
        # on_delete: dedup ledger rows are meaningless once the tenant
        # itself is gone — same CASCADE convention as every other
        # company-scoped model (checked in YDATA1/2's on_delete sweep).
        on_delete=models.CASCADE,
        related_name='core_processedwebhookevent_set',
        verbose_name='Société',
    )
    source = models.CharField('Source', max_length=100)
    event_id = models.CharField('Event ID', max_length=200)
    created_at = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        verbose_name = 'Événement webhook traité'
        verbose_name_plural = 'Événements webhook traités'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'source', 'event_id'],
                name='core_processedwebhookevent_unique',
            ),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.source}:{self.event_id}'


def dedupe_event(*, company, source: str, event_id: str) -> bool:
    """Tente d'enregistrer CET événement comme "en cours de traitement".

    Renvoie ``True`` si c'est la PREMIÈRE fois que ce triplet est vu — le
    code appelant doit alors procéder normalement à ses effets de bord.
    Renvoie ``False`` si ce triplet a déjà été enregistré (course perdue ou
    rejeu) — l'appelant doit répondre "déjà traité" SANS rejouer l'effet.

    L'insertion se fait DANS ``transaction.atomic()`` avant tout effet : deux
    arrivées concurrentes ne peuvent jamais toutes deux gagner (la 2ᵉ lève
    IntegrityError sur la contrainte unique DB, pas une simple lecture
    optimiste)."""
    try:
        with transaction.atomic():
            ProcessedWebhookEvent.objects.create(
                company=company, source=source, event_id=event_id,
            )
        return True
    except IntegrityError:
        return False


# ─────────────────────────────────────────────────────────────────────────
# YAPIC9 — mixin d'idempotence réutilisable pour tout endpoint de création
# interne (`Idempotency-Key`).
# ─────────────────────────────────────────────────────────────────────────

IDEMPOTENCY_KEY_HEADER = 'HTTP_IDEMPOTENCY_KEY'


class IdempotencyRecord(models.Model):
    """YAPIC9 — mémorise la réponse d'un POST de création INTERNE (JWT) pour
    un en-tête ``Idempotency-Key`` donné, scopé par ``(company, endpoint,
    key)``. Rejouer le MÊME triplet avec un corps IDENTIQUE renvoie la
    réponse mémorisée (pas de nouvelle création) ; un corps DIFFÉRENT → 409.

    C'est LE modèle foundation partagé que XPLT5 (``apps/publicapi``) aurait
    dû réutiliser plutôt que d'en créer un second scopé par ``ApiKey`` — les
    deux couvrent des périmètres distincts (API publique par clé vs POST
    interne JWT) et coexistent, un seul modèle par périmètre.

    Champs déclarés directement (voir ``ProcessedWebhookEvent`` ci-dessus
    pour la même raison : éviter l'import circulaire avec ``core/models.py``,
    qui réexporte ce modèle en tout dernier)."""

    company = models.ForeignKey(
        'authentication.Company',
        # on_delete: le ledger d'idempotence n'a plus de sens une fois le
        # tenant supprimé — même convention CASCADE que partout ailleurs.
        on_delete=models.CASCADE,
        related_name='core_idempotencyrecord_set',
        verbose_name='Société',
    )
    key = models.CharField('Clé', max_length=255)
    endpoint = models.CharField('Endpoint', max_length=200)
    request_fingerprint = models.CharField('Empreinte requête', max_length=64)
    response_status = models.IntegerField('Statut réponse')
    response_body = models.JSONField('Corps réponse', default=dict, blank=True)
    created_at = models.DateTimeField('Créé le', auto_now_add=True)

    class Meta:
        verbose_name = "Enregistrement d'idempotence"
        verbose_name_plural = "Enregistrements d'idempotence"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'endpoint', 'key'],
                name='core_idempotencyrecord_unique',
            ),
        ]

    def __str__(self):
        return f'{self.endpoint}:{self.key}'


class IdempotencyConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "Cette « Idempotency-Key » a déjà été utilisée avec un corps de "
        "requête différent."
    )
    default_code = 'idempotency_conflict'


def _fingerprint(body) -> str:
    canonical = json.dumps(body, default=str, sort_keys=True).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


class IdempotentCreateMixin:
    """Mixin OPT-IN : un ``ModelViewSet`` qui en hérite (AVANT
    ``CreateModelMixin``/``ModelViewSet`` dans son MRO — l'ordre des bases
    Python détermine quelle ``create()`` gagne) gagne le contrat
    ``Idempotency-Key`` sur son action ``create`` SANS toucher à
    ``perform_create``.

    Sans en-tête ``Idempotency-Key`` : comportement ACTUEL inchangé (chemin
    normal, aucune requête DB supplémentaire). Avec l'en-tête :
      * clé déjà vue + corps IDENTIQUE (même empreinte) -> la réponse
        mémorisée est rejouée, AUCUNE nouvelle création ;
      * clé déjà vue + corps DIFFÉRENT -> 409 ``IdempotencyConflict`` ;
      * clé neuve -> le ``create()`` normal s'exécute, puis la réponse est
        mémorisée pour un rejeu futur.

    ``company`` est TOUJOURS résolue serveur (``request.user.company``),
    jamais acceptée du corps de requête — la clé est scopée par
    ``(company, endpoint)``, donc jamais partagée entre sociétés."""

    def _idempotency_key(self, request):
        raw = (request.META.get(IDEMPOTENCY_KEY_HEADER)
               or request.headers.get('Idempotency-Key'))
        return raw.strip()[:255] if raw else None

    def _idempotency_endpoint(self):
        return f'{self.__class__.__module__}.{self.__class__.__qualname__}'

    def create(self, request, *args, **kwargs):
        idem_key = self._idempotency_key(request)
        if not idem_key:
            return super().create(request, *args, **kwargs)

        from rest_framework.response import Response

        company = getattr(request.user, 'company', None)
        endpoint = self._idempotency_endpoint()
        fingerprint = _fingerprint(request.data)

        existing = IdempotencyRecord.objects.filter(
            company=company, endpoint=endpoint, key=idem_key).first()
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflict()
            return Response(
                existing.response_body, status=existing.response_status)

        response = super().create(request, *args, **kwargs)
        try:
            IdempotencyRecord.objects.get_or_create(
                company=company, endpoint=endpoint, key=idem_key,
                defaults={
                    'request_fingerprint': fingerprint,
                    'response_status': response.status_code,
                    'response_body': response.data,
                },
            )
        except Exception:  # noqa: BLE001 — l'idempotence est un CONFORT, ne
            # doit jamais faire échouer une création qui a déjà réussi.
            pass
        return response
