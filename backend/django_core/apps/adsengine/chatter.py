"""PUB55 — Fil de chatter par entité (campagne / ad set / ad).

Un fil chronologique UNIQUE qui mêle :
  * les NOTES manuelles (``AdEngineActivity`` — acteur + société côté serveur) ;
  * les événements AUTO déjà persistés — ``EngineAction`` APPLIQUÉES ciblant
    l'entité (« action appliquée ») et ``EngineAlert`` de l'entité (« alerte »).

Les événements auto ne sont PAS dupliqués en base : on les FUSIONNE à la lecture
depuis leurs tables d'origine (traçabilité intacte). Lecture seule, company-scopé.
"""
from __future__ import annotations


def _action_targets(action, meta_id):
    """Vrai si une ``EngineAction`` cible l'entité ``meta_id`` (n'importe quelle
    clé de son payload portant l'id : target_meta_id / campaign_id / adset_id /
    object_id…)."""
    payload = action.payload or {}
    return any(str(v) == str(meta_id) for v in payload.values())


def build_timeline(company, entity_type, entity_meta_id):
    """PUB55 — Fil fusionné (le plus récent d'abord) pour une entité.

    Renvoie une liste de dicts
    ``{kind, body, at, author, source}`` où ``kind`` ∈
    {note, action_applied, alert}. ``at`` est ISO-8601. Company-scopé."""
    from .models import AdEngineActivity, EngineAction, EngineAlert

    items = []

    # 1. Notes manuelles.
    notes = AdEngineActivity.objects.filter(
        company=company, entity_type=entity_type,
        entity_meta_id=str(entity_meta_id)).select_related('user')
    for n in notes:
        items.append({
            'kind': 'note', 'body': n.body,
            'at': n.created_at.isoformat(),
            'author': (getattr(n.user, 'username', None) if n.user_id else None),
            'source': 'note',
        })

    # 2. Actions APPLIQUÉES ciblant l'entité (événement auto).
    applied = EngineAction.objects.filter(
        company=company, status=EngineAction.Statut.APPLIQUEE)
    for a in applied:
        if not _action_targets(a, entity_meta_id):
            continue
        at = a.applied_at or a.created_at
        items.append({
            'kind': 'action_applied',
            'body': f'{a.get_kind_display()} — {a.reason_fr}',
            'at': at.isoformat(),
            'author': None, 'source': 'action', 'auto': a.auto,
        })

    # 3. Alertes de l'entité (clé 'type:meta_id').
    entity_key = f'{entity_type}:{entity_meta_id}'
    alerts = EngineAlert.objects.filter(company=company, entity_key=entity_key)
    for al in alerts:
        items.append({
            'kind': 'alert',
            'body': al.message,
            'at': al.created_at.isoformat(),
            'author': None, 'source': 'alert',
            'severity': al.severity,
        })

    items.sort(key=lambda i: i['at'], reverse=True)
    return items
