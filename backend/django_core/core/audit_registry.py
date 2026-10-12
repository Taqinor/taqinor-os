"""Registre GÉNÉRIQUE du journal d'audit (ENF20) — même inversion de
dépendance que ``core.notify_registry`` : ``core`` reste fondation (contrat
import-linter ``core-foundation-is-a-base-layer``) et ne connaît AUCUNE app,
y compris ``apps.audit``.

``apps.audit`` enregistre ``recorder.record`` / ``recorder.current_user`` dans
SON PROPRE ``ready()`` ; les apps dont un chemin transitif part de ``ventes``
(stock, automation, dataimport — contrat ``ventes-does-not-import-audit``)
appellent CE registre au lieu d'importer ``apps.audit``. L'action est passée
en STRING LITTÉRAL (la valeur brute d'``apps.audit.models.AuditLog.Action`` —
``'update'``, ``'create'``, ``'security_alert'``…, jamais l'enum importé) ;
``AuditLog.Action`` étant un ``TextChoices``, la ligne écrite est identique.

Les arguments sont relayés TELS QUELS : aucun défaut n'est injecté, pour que
``recorder.record`` distingue toujours « ``user`` non fourni » (acteur courant)
de ``user=None`` (action système).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Callable(action, **kwargs) — ``apps.audit.recorder.record`` (best-effort).
# None = no-op silencieux (app audit non chargée — jamais une exception).
_RECORD = None
# Callable() -> user|None — ``apps.audit.recorder.current_user``.
_CURRENT_USER = None


def enregistrer(fn, current_user=None) -> None:
    """Enregistre l'enregistreur réel (idempotent : remplace l'existant)."""
    global _RECORD, _CURRENT_USER
    _RECORD = fn
    _CURRENT_USER = current_user


def desenregistrer() -> None:
    """Retire l'enregistreur (test uniquement — isole le registre)."""
    global _RECORD, _CURRENT_USER
    _RECORD = None
    _CURRENT_USER = None


def record(*args, **kwargs):
    """Relaie vers l'enregistreur. No-op (log debug) si aucun n'est enregistré."""
    if _RECORD is None:
        logger.debug(
            'core.audit_registry.record: aucun enregistreur (%s).',
            args[0] if args else kwargs.get('action'))
        return None
    return _RECORD(*args, **kwargs)


def current_user():
    """Acteur de la requête courante, ou None (aucun enregistreur)."""
    if _CURRENT_USER is None:
        return None
    return _CURRENT_USER()
