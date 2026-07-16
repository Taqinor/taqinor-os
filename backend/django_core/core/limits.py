"""NTPLT7 — Limites douces par tenant (enforcement DOUX, jamais de blocage dur).

``verifier(company, cle, courant)`` compare la consommation ``courant`` au
plafond configuré (``core.TenantLimit``) pour une société. En cas de
dépassement :

* les admins de la société sont NOTIFIÉS (via un notifieur enregistré — voir
  plus bas) ;
* l'appelant (dataimport / exports / upload) pose un en-tête
  ``X-Quota-Warning`` sur sa réponse à partir de la valeur renvoyée.

JAMAIS de blocage : la fonction ne lève pas, ne refuse pas — elle signale. Un
plafond à ``0`` = illimité (aucun avertissement).

``core`` reste fondation : ce module n'importe AUCUNE app (ni notifications, ni
domaine). Les notifications passent par un NOTIFIEUR ENREGISTRÉ que l'app
``notifications`` branche dans son ``ready()`` (même pattern que
``core.retention`` / ``core.cache``) — sans cela, un dépassement est seulement
journalisé.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Notifieur enregistré : callable(company, cle, courant, limite) -> None.
# Peuplé par l'app notifications dans son ``ready()`` ; ``None`` = simple log.
_NOTIFIER = None


def register_limit_notifier(fn) -> None:
    """Enregistre le notifieur appelé sur dépassement (idempotent : remplace).

    ``fn(company, cle, courant, limite)`` est responsable de créer les
    notifications aux admins de la société. ``core`` ne connaît que ce
    callable — jamais l'app notifications."""
    global _NOTIFIER
    _NOTIFIER = fn


def clear_limit_notifier() -> None:
    """Retire le notifieur (test uniquement)."""
    global _NOTIFIER
    _NOTIFIER = None


def get_limit(company, cle) -> int:
    """Plafond configuré pour ``(company, cle)`` — ``0`` (illimité) si absent."""
    from .models import TenantLimit
    row = TenantLimit.objects.filter(company=company, cle=cle).first()
    return int(row.valeur) if row else 0


def verifier(company, cle, courant) -> dict:
    """Vérifie ``courant`` contre le plafond ``cle`` de ``company``.

    Renvoie un dict ``{cle, limite, courant, depasse, warning}`` :
      * ``depasse`` — True si ``limite > 0`` ET ``courant > limite`` ;
      * ``warning`` — chaîne prête pour l'en-tête ``X-Quota-Warning`` (vide si
        pas de dépassement).
    Sur dépassement, notifie les admins (best-effort). Ne lève JAMAIS.
    """
    limite = get_limit(company, cle)
    depasse = bool(limite > 0 and courant is not None and courant > limite)
    warning = ''
    if depasse:
        warning = (f'{cle}: {courant} dépasse le plafond {limite} '
                   f'(consommation tolérée, non bloquée)')
        _notify(company, cle, courant, limite)
    return {
        'cle': cle, 'limite': limite, 'courant': courant,
        'depasse': depasse, 'warning': warning,
    }


def _notify(company, cle, courant, limite) -> None:
    """Notifie les admins du dépassement (best-effort, via le notifieur)."""
    if _NOTIFIER is None:
        logger.info('TenantLimit dépassée (aucun notifieur): société=%s '
                    'cle=%s courant=%s limite=%s',
                    getattr(company, 'id', company), cle, courant, limite)
        return
    try:
        _NOTIFIER(company, cle, courant, limite)
    except Exception:  # noqa: BLE001 — une notif KO ne casse jamais l'appelant
        logger.exception('TenantLimit: notifieur en échec (société=%s cle=%s)',
                         getattr(company, 'id', company), cle)
