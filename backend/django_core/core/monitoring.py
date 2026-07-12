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

import contextvars
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Drapeau idempotent : ``init_sentry`` ne s'exécute qu'une fois par process.
_INITIALISE = False

# NTPLT46 — société courante (contextvar) pour tagger chaque événement Sentry.
# Posée là où le contexte tenant est déjà résolu (``set_current_company`` —
# middleware RLS + ``tenant_task`` Celery), JAMAIS par une résolution ajoutée au
# chemin par défaut (aucun coût nouveau par requête). ``before_send`` lit ce
# contextvar au moment de la capture d'une erreur.
_company_id_ctx: "contextvars.ContextVar[Optional[int]]" = (
    contextvars.ContextVar('sentry_company_id', default=None))


def sentry_dsn():
    """DSN Sentry configuré (chaîne vide = monitoring désactivé)."""
    return (os.environ.get('SENTRY_DSN') or '').strip()


def is_enabled():
    """Vrai uniquement si un DSN est configuré."""
    return bool(sentry_dsn())


def bind_company(company_id: Optional[int]) -> None:
    """NTPLT46 — associe la société courante aux futurs événements Sentry.

    No-op inoffensif si Sentry n'est pas initialisé (aucun import du SDK). Appelé
    depuis ``core.tenant_context.set_current_company`` : le tag suit exactement le
    contexte tenant déjà posé, sans travail supplémentaire sur le chemin nominal.
    """
    _company_id_ctx.set(company_id)
    if not _INITIALISE:
        return
    try:
        import sentry_sdk  # noqa: WPS433 — paresseux, présent seulement si init
        sentry_sdk.set_tag('company', str(company_id) if company_id else None)
    except Exception:  # noqa: BLE001 — jamais casser une requête pour un tag
        pass


def _before_send(event, hint):
    """Injecte le tag ``company`` sur chaque événement (repli contextvar)."""
    try:
        company_id = _company_id_ctx.get()
        if company_id is not None:
            tags = event.setdefault('tags', {})
            tags.setdefault('company', str(company_id))
    except Exception:  # noqa: BLE001 — un before_send ne doit jamais lever
        pass
    return event


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
    # NTPLT46 — échantillonnage de traces BAS par défaut (5 %) : de la
    # performance/tracing sans le coût/volume d'un 100 %. Surchargable par
    # SENTRY_TRACES_SAMPLE_RATE (ex. '0' pour couper le tracing).
    try:
        traces = float(
            os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.05') or '0.05')
    except (TypeError, ValueError):
        traces = 0.05
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get('SENTRY_ENVIRONMENT', '') or None,
        traces_sample_rate=traces,
        send_default_pii=False,
        # NTPLT46 — chaque événement porte le tag `company` (repli contextvar).
        before_send=_before_send,
    )
    _INITIALISE = True
    logger.info('Monitoring Sentry initialisé.')
    return True
