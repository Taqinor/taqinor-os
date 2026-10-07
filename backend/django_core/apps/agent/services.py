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

import hashlib
import hmac
import json
import os
from typing import Any, Callable, Dict, Optional

from django.conf import settings
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


# ── AANA18 — preuve qu'une confirmation a REELLEMENT ete emise par l'agent ────
# C-AANA-008 : ``POST /agent/logs/confirmer/`` acceptait n'importe quel corps
# d'un utilisateur authentifie. Un compte SANS ``crm_creer`` forgeait un journal
# ``crm.client.create`` pointant sur un client PREEXISTANT ; l'annulation par un
# admin SUPPRIMAIT ensuite ce client (sonde du 05/10 : 201 puis suppression).
# Desormais le relais FastAPI signe, APRES l'execution reelle, une preuve HMAC
# avec un secret partage (``AGENT_HMAC_SECRET``, jamais expose au navigateur) ;
# Django la recalcule pour l'utilisateur et la societe de LA REQUETE. Sans
# secret configure : toute confirmation est refusee (fail-closed). Format
# canonique (identique des deux cotes, verifie par le contrat
# ``contract_samples/logs_confirmer.json``) : JSON trie, compact, UTF-8 de
# {v, action_key, company_id, user_id, inputs, object_id} ; HMAC-SHA256 hex.
PREUVE_VERSION = 1


def agent_hmac_secret() -> str:
    """Secret partage Django <-> FastAPI ('' si non configure)."""
    return (getattr(settings, 'AGENT_HMAC_SECRET', '')
            or os.environ.get('AGENT_HMAC_SECRET', '') or '')


def message_preuve_confirmation(*, action_key: str, company_id: int,
                                user_id: int, inputs: Optional[Dict[str, Any]],
                                object_id: Any) -> str:
    """Message canonique signe (meme octets que cote FastAPI)."""
    return json.dumps(
        {
            'v': PREUVE_VERSION,
            'action_key': action_key,
            'company_id': int(company_id),
            'user_id': int(user_id),
            'inputs': inputs or {},
            'object_id': '' if object_id in (None, '') else str(object_id),
        },
        sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    )


def calculer_preuve_confirmation(*, secret: str, **champs) -> str:
    return hmac.new(
        secret.encode('utf-8'),
        message_preuve_confirmation(**champs).encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def preuve_confirmation_valide(preuve: Any, **champs) -> bool:
    """True si ``preuve`` est la signature de ces champs par le secret partage.
    Fail-closed : secret absent, preuve absente ou mal formee -> False."""
    secret = agent_hmac_secret()
    if not secret or not isinstance(preuve, str) or not preuve:
        return False
    try:
        attendue = calculer_preuve_confirmation(secret=secret, **champs)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(preuve, attendue)


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
