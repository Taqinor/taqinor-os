"""FG396 — Monitoring d'erreurs applicatives (Sentry), gardé par DSN.

Couche de FONDATION : initialise la supervision d'erreurs UNIQUEMENT si un DSN
est configuré. Sans ``SENTRY_DSN`` (le cas par défaut), c'est un NO-OP TOTAL :
aucune dépendance n'est chargée, aucune donnée n'est envoyée, aucun appel réseau
n'a lieu — la fonctionnalité « ne fait rien » plutôt que de casser. L'import du
SDK est PARESSEUX (à l'intérieur de la fonction) et tolérant à son absence : si
``sentry-sdk`` n'est pas installé, l'init est silencieusement ignorée.

Activation (étape du fondateur, dépendance optionnelle) :
  1. ``pip install sentry-sdk`` (DEP) ;
  2. renseigner ``SENTRY_DSN`` (+ éventuellement ``SENTRY_ENVIRONMENT`` /
     ``SENTRY_TRACES_SAMPLE_RATE``) dans l'environnement.

Aucune importation d'app domaine : ``core`` reste une couche de base.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Drapeau idempotent : ``init_sentry`` ne s'exécute qu'une fois par process.
_INITIALISE = False


def sentry_dsn():
    """DSN Sentry configuré (chaîne vide = monitoring désactivé)."""
    return (os.environ.get('SENTRY_DSN') or '').strip()


def is_enabled():
    """Vrai uniquement si un DSN est configuré."""
    return bool(sentry_dsn())


def init_sentry():
    """Initialise Sentry si (et seulement si) un DSN est configuré.

    No-op total quand le DSN est absent ou quand ``sentry-sdk`` n'est pas
    installé. Idempotent. Renvoie ``True`` si l'init a réellement eu lieu.
    """
    global _INITIALISE
    if _INITIALISE:
        return True
    dsn = sentry_dsn()
    if not dsn:
        return False
    try:
        import sentry_sdk  # noqa: WPS433 — import paresseux, dépendance optionnelle
    except Exception:  # noqa: BLE001 — paquet absent → no-op silencieux
        logger.info(
            'SENTRY_DSN défini mais sentry-sdk introuvable — monitoring ignoré.')
        return False
    try:
        traces = float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0') or '0')
    except (TypeError, ValueError):
        traces = 0.0
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get('SENTRY_ENVIRONMENT', '') or None,
        traces_sample_rate=traces,
        send_default_pii=False,
    )
    _INITIALISE = True
    logger.info('Monitoring Sentry initialisé.')
    return True
