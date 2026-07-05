"""YHARD2 — services d'écriture pour le journal des actions IA confirmées.

Deux responsabilités :

  * :func:`log_confirmed_action` — appelée au moment où une action proposée
    par l'agent est CONFIRMÉE par l'utilisateur (jamais à la simple
    proposition, qui reste éphémère côté agent/Redis, hors périmètre ici).
    Crée une ``AgentActionLog`` scopée société, avec la cible résultante si
    fournie ;
  * :func:`annuler_action` — pour une action réversible (``risk_level`` !=
    ``irreversible``) non déjà annulée, inverse son effet en appelant un
    HANDLER DE ROLLBACK enregistré par la clé d'action, puis marque
    ``undone_at``. Refuse toute action irréversible ou déjà annulée.

Aucune app métier n'est importée ICI (satellite technique, jamais importé par
une app de domaine) : un handler de rollback est du code appartenant à l'app
métier concernée, enregistré dans ce module via :func:`register_undo_handler`
— exactement le même motif que ``apps.agent.registry`` (registre en mémoire,
alimenté par les apps qui en ont besoin, jamais l'inverse).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from django.utils import timezone

from .models import AgentActionLog

# Registre des handlers de rollback, indexé par action_key. Chaque handler est
# une fonction ``(log: AgentActionLog) -> str`` qui inverse l'effet de
# l'action et renvoie un court détail texte (journalisé dans ``undo_detail``).
# Alimenté par les apps métier via :func:`register_undo_handler` (jamais
# l'inverse — cette app reste dépendance-descendante uniquement).
_UNDO_HANDLERS: Dict[str, Callable[[AgentActionLog], str]] = {}


def register_undo_handler(action_key: str, handler: Callable[[AgentActionLog], str]):
    """Enregistre (idempotent — dernier appel gagne) un handler de rollback
    pour ``action_key``. Utilisable comme fonction directe ou décorateur."""
    _UNDO_HANDLERS[action_key] = handler
    return handler


def has_undo_handler(action_key: str) -> bool:
    return action_key in _UNDO_HANDLERS


class ActionNotUndoableError(Exception):
    """Levée quand l'annulation est refusée (irréversible / déjà annulée /
    aucun handler enregistré)."""


def log_confirmed_action(
    *, company, user, action_key: str, risk_level: str,
    inputs: Optional[Dict[str, Any]] = None, proposal_hash: str = '',
    proposed_at=None, resulted_object=None,
) -> AgentActionLog:
    """Journalise la confirmation d'une action IA (société forcée par
    l'appelant — jamais déduite du corps de requête). ``resulted_object`` est
    l'instance créée/modifiée par l'action, si connue au moment de l'appel
    (content_type + object_id + repr dérivés automatiquement)."""
    content_type = None
    object_id = ''
    object_repr = ''
    if resulted_object is not None:
        from django.contrib.contenttypes.models import ContentType
        content_type = ContentType.objects.get_for_model(resulted_object.__class__)
        object_id = str(getattr(resulted_object, 'pk', '') or '')
        try:
            object_repr = str(resulted_object)[:255]
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            object_repr = ''

    return AgentActionLog.objects.create(
        company=company,
        user=user if (user and getattr(user, 'is_authenticated', False)) else None,
        action_key=action_key,
        risk_level=risk_level,
        proposal_hash=proposal_hash or '',
        inputs_json=inputs or {},
        proposed_at=proposed_at,
        executed_at=timezone.now(),
        content_type=content_type,
        object_id=object_id,
        object_repr=object_repr,
    )


def annuler_action(log: AgentActionLog, *, user=None) -> AgentActionLog:
    """Annule une action réversible. Lève :class:`ActionNotUndoableError` si
    l'action est irréversible, déjà annulée, ou sans handler enregistré pour
    sa ``action_key`` (fail-closed — jamais un no-op silencieux qui ferait
    croire à un rollback qui n'a pas eu lieu)."""
    if log.risk_level == AgentActionLog.RiskLevel.IRREVERSIBLE:
        raise ActionNotUndoableError(
            f"L'action « {log.action_key} » est irréversible — annulation refusée.")
    if log.is_undone:
        raise ActionNotUndoableError(
            f"L'action « {log.action_key} » (log #{log.pk}) a déjà été annulée.")

    handler = _UNDO_HANDLERS.get(log.action_key)
    if handler is None:
        raise ActionNotUndoableError(
            f"Aucun handler de rollback enregistré pour « {log.action_key} ».")

    detail = handler(log) or ''
    log.undone_at = timezone.now()
    log.undo_detail = detail
    log.save(update_fields=['undone_at', 'undo_detail'])
    return log
