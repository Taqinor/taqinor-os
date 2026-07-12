"""NTPLT43 — logs JSON structurés taggés tenant.

``TenantLogFilter`` injecte le contexte de la requête courante (request_id,
company_id, user_id, path, status, duration_ms) dans CHAQUE enregistrement de
log — de sorte qu'une ligne de log applicative porte toujours le tenant et la
requête qui l'a produite. ``JSONFormatter`` sérialise le tout en une ligne JSON
ingérable telle quelle par Loki / CloudWatch / ELK.

Activation (``settings`` gèrent le câblage) : ``LOG_FORMAT=json``. Par défaut, le
format actuel reste INCHANGÉ (aucune config LOGGING nouvelle n'est posée).
"""
from __future__ import annotations

import json
import logging

from .observability import current_context

# Champs de contexte injectés sur chaque record (valeur par défaut si hors requête).
_CONTEXT_FIELDS = (
    'request_id', 'company_id', 'user_id', 'path', 'status', 'duration_ms')


class TenantLogFilter(logging.Filter):
    """Ajoute les attributs de contexte tenant à chaque enregistrement."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = current_context()
        for field in _CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, ctx.get(field))
        return True


class JSONFormatter(logging.Formatter):
    """Formate un enregistrement en une ligne JSON (une par log)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def build_logging_config(level: str = 'INFO') -> dict:
    """Config LOGGING JSON complète (console) — utilisée quand LOG_FORMAT=json."""
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {
            'tenant': {'()': 'core.logging_ext.TenantLogFilter'},
        },
        'formatters': {
            'json': {'()': 'core.logging_ext.JSONFormatter'},
        },
        'handlers': {
            'console_json': {
                'class': 'logging.StreamHandler',
                'formatter': 'json',
                'filters': ['tenant'],
            },
        },
        'root': {
            'handlers': ['console_json'],
            'level': level,
        },
        'loggers': {
            'django': {
                'handlers': ['console_json'],
                'level': 'WARNING',
                'propagate': False,
            },
            # NTPLT24 — exceptions Redis ignorées, remontées ici en WARNING.
            'django_redis': {
                'handlers': ['console_json'],
                'level': 'WARNING',
                'propagate': False,
            },
        },
    }
