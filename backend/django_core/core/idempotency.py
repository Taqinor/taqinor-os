"""YDATA12 — infra idempotence WEBHOOKS ENTRANTS : `ProcessedWebhookEvent` +
insertion dans la transaction AVANT tout effet, réutilisable par tout
endpoint entrant.

Distinct de deux mécanismes voisins déjà dans le repo (jamais réécrits ici) :
  * ``core/webhooks.py`` — dispatch SORTANT de webhooks signés (existant).
  * ``core.ProcessedEvent`` (``core/models.py``, NTPLT9/10) — dédup du
    CONSOMMATEUR du bus d'événements interne (``event_id`` + ``handler_name``,
    sans FK company) : ce n'est PAS le même périmètre (webhooks EXTERNES
    entrants, scopés par société + source du provider).
  * ``apps/publicapi/idempotency.py`` (XPLT5) — idempotence des ÉCRITURES de
    l'API PUBLIQUE PAR CLÉ API (``Idempotency-Key`` client). Différent aussi
    de YAPIC9 (``core.IdempotencyRecord`` — POST internes JWT-authentifiés).

``dedupe_event`` insère la ligne (contrainte unique
``(company, source, event_id)``) DANS une transaction, AVANT tout effet de
bord : la 2ᵉ arrivée concurrente lève IntegrityError → l'appelant répond
"déjà traité" (200) sans rejouer l'effet, au lieu du pattern
lecture-puis-décision (race condition classique).
"""
from __future__ import annotations

from django.db import IntegrityError, models, transaction


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
