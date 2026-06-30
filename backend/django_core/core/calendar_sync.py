"""FG374 — Sync calendrier Google/Outlook (2-way), fondation branchable.

Synchronise les événements locaux (poses/interventions/visites — agrégés par
``apps.reporting.calendar``) avec un calendrier externe SANS que ``core``
n'importe ``reporting`` ni aucune app métier (contrat import-linter
``core-foundation-is-a-base-layer``).

Découplage par DICTS d'événements
---------------------------------

L'appelant (côté ``reporting``) passe une liste d'événements sous forme de
DICTS purs ``{"kind", "id", "title", "start", "end", "location", ...}``.
``core`` ne connaît AUCUN modèle métier : il calcule un hash par événement,
le compare au dernier état synchronisé (``CalendarSyncMapping``) et ne pousse
au connecteur que les créations / mises à jour réelles (idempotence).

⚠ AUTH : la sync réelle exige une autorisation OAuth Google/Outlook (jeton)
que seul le fondateur provisionne. Sans connecteur configuré → ``push_events``
calcule les diffs mais NE fait aucun appel réseau (dry-run propre).
"""
from __future__ import annotations

import hashlib
import json

from django.utils import timezone

from .integrations import (
    TYPE_CALENDAR,
    BaseProvider,
    provider_from_config,
    register_provider,
)


def event_hash(event: dict) -> str:
    """Empreinte stable d'un événement (clés triées → SHA-256 court)."""
    payload = json.dumps(event, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:64]


class CalendarProvider(BaseProvider):
    """Base d'un connecteur de calendrier externe (fondation)."""

    integration_type = TYPE_CALENDAR

    def upsert_event(self, event: dict, external_event_id: str = '') -> dict:
        raise NotImplementedError  # pragma: no cover

    def delete_event(self, external_event_id: str) -> dict:
        raise NotImplementedError  # pragma: no cover

    def list_events(self) -> list[dict]:
        raise NotImplementedError  # pragma: no cover


@register_provider
class GenericCalendarProvider(CalendarProvider):
    """Connecteur calendrier générique, configurable (FG374).

    Non configuré → no-op propre (``ok=False``, aucun appel réseau). À spécialiser
    pour Google/Outlook (sous-classe enregistrée) une fois l'OAuth provisionné.
    """

    code = 'generic'
    label = 'Calendrier générique'

    def is_configured(self) -> bool:
        return bool(self.secret)

    def upsert_event(self, event: dict, external_event_id: str = '') -> dict:
        if not self.is_configured():
            return {'ok': False, 'detail': 'Calendrier non configuré.'}
        return {'ok': True, 'external_event_id': external_event_id or 'evt'}

    def delete_event(self, external_event_id: str) -> dict:
        if not self.is_configured():
            return {'ok': False, 'detail': 'Calendrier non configuré.'}
        return {'ok': True}

    def list_events(self) -> list[dict]:
        if not self.is_configured():
            return []
        return []


def _active_calendar_config(company):
    from .models import IntegrationConfig
    return (IntegrationConfig.objects
            .filter(company=company, integration_type=TYPE_CALENDAR, actif=True)
            .order_by('id')
            .first())


def push_events(company, events, *, provider=None):
    """Pousse des événements locaux vers le calendrier externe (idempotent).

    ``events`` : liste de dicts ``{"kind", "id", ...}`` (fournis par l'appelant —
    AUCUN modèle métier importé). Calcule un diff via ``CalendarSyncMapping`` :
    seuls les événements nouveaux ou modifiés (hash différent) sont poussés.

    Multi-tenant : société imposée par l'appelant. Sans connecteur configuré,
    fait un dry-run (compte les diffs sans appel réseau). Retourne
    ``{"created", "updated", "skipped"}``.
    """
    from .models import CalendarSyncMapping

    cfg = _active_calendar_config(company)
    prov_code = provider or (cfg.provider if cfg else GenericCalendarProvider.code)
    connector = None
    if cfg is not None and cfg.provider == prov_code:
        connector = provider_from_config(cfg)
    else:
        from .integrations import get_provider_class
        cls = get_provider_class(TYPE_CALENDAR, prov_code)
        connector = cls() if cls else None

    created = updated = skipped = 0
    for event in events:
        kind = str(event.get('kind', ''))
        local_id = str(event.get('id', ''))
        if not kind or not local_id:
            skipped += 1
            continue
        h = event_hash(event)
        mapping, is_new = CalendarSyncMapping.objects.get_or_create(
            company=company, provider=prov_code,
            local_kind=kind, local_id=local_id)
        if not is_new and mapping.last_hash == h:
            skipped += 1
            continue
        # Pousser (réel si configuré, sinon dry-run).
        ext_id = mapping.external_event_id
        if connector is not None and connector.is_configured():
            res = connector.upsert_event(event, external_event_id=ext_id)
            if res.get('ok'):
                mapping.external_event_id = res.get('external_event_id',
                                                    ext_id) or ext_id
        mapping.last_hash = h
        mapping.last_synced_le = timezone.now()
        mapping.save()
        if is_new:
            created += 1
        else:
            updated += 1
    return {'created': created, 'updated': updated, 'skipped': skipped}
