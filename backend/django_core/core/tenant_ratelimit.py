"""NTPLT26 — Équité Celery par tenant (token bucket Redis).

Une société qui lance 500 rendus PDF ne doit pas monopoliser les workers et
bloquer les rendus interactifs des autres tenants. ``tenant_ratelimit`` est un
seau à jetons (token bucket) simple, par ``(company_id, famille)``, stocké
dans le cache Redis : consulté en TÊTE des familles de tâches lourdes (rendu
PDF, exports xlsx, OCR), il dit si la tâche peut s'exécuter maintenant ou doit
se re-planifier avec un ``countdown``.

Contrat
-------
* ``consume(company_id, famille, max_par_min=None)`` renvoie
  ``(ok, retry_in)`` :
  - ``ok=True``  → un jeton a été consommé, la tâche s'exécute ;
  - ``ok=False`` → budget épuisé ; ``retry_in`` = secondes avant re-tentative.
* ``max_par_min`` : budget par minute ; défaut par famille lu de
  ``settings.TENANT_TASK_RATE_LIMITS`` (généreux). ``0`` = illimité (off).
* ``guard_task(famille)`` : décorateur d'une tâche Celery bindée ; si le
  budget est épuisé, la tâche se ``self.retry(countdown=retry_in)``.

Dégradation : si le cache est indisponible (Redis down), on AUTORISE
(fail-open) — l'équité est un confort, jamais un point de panne bloquant.

``core`` reste fondation : aucun import d'app métier.
"""
from __future__ import annotations

import functools
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Budgets par défaut (tâches/minute/société) par famille. Généreux : l'équité
# ne mord que sur un abus massif. Surchageable via settings.
_DEFAULT_LIMITS = {
    'pdf': 60,
    'xlsx': 30,
    'ocr': 60,
}

# Fenêtre du seau, en secondes (budget exprimé « par minute »).
_WINDOW_SECONDS = 60


def limit_for(famille: str) -> int:
    """Budget/minute effectif d'une famille (settings > défaut ; 0 = off)."""
    configured = getattr(settings, 'TENANT_TASK_RATE_LIMITS', None)
    if isinstance(configured, dict) and famille in configured:
        try:
            return int(configured[famille])
        except (TypeError, ValueError):
            pass
    return _DEFAULT_LIMITS.get(famille, 0)


def _bucket_key(company_id, famille: str) -> str:
    """Clé cache du seau, alignée par fenêtre pour une expiration naturelle."""
    import time
    window = int(time.time()) // _WINDOW_SECONDS
    scope = company_id if company_id is not None else 'sys'
    return f'ratelimit:{famille}:{scope}:{window}'


def consume(company_id, famille: str, max_par_min: int = None):
    """Tente de consommer un jeton pour ``(company_id, famille)``.

    Renvoie ``(ok: bool, retry_in: int)``. ``max_par_min=0`` (ou budget non
    configuré) → toujours autorisé. Fail-open si le cache est KO.
    """
    budget = max_par_min if max_par_min is not None else limit_for(famille)
    if not budget or budget <= 0:
        return True, 0
    key = _bucket_key(company_id, famille)
    try:
        # ``add`` ne pose la clé qu'à la première consommation de la fenêtre,
        # avec un TTL = fenêtre → le compteur disparaît tout seul.
        cache.add(key, 0, _WINDOW_SECONDS)
        used = cache.incr(key)
    except Exception:  # noqa: BLE001 — cache KO → fail-open (autorise)
        logger.warning('tenant_ratelimit fail-open: %s/%s', company_id,
                       famille)
        return True, 0
    if used > budget:
        # Budget dépassé : re-planifier au début de la fenêtre suivante.
        import time
        retry_in = _WINDOW_SECONDS - (int(time.time()) % _WINDOW_SECONDS)
        return False, max(1, retry_in)
    return True, 0


def guard_task(famille: str):
    """Décorateur pour une tâche Celery BINDÉE (``bind=True``).

    Consulte le budget de la société (kwarg ``company_id`` de la tâche) en tête
    d'exécution ; si épuisé, ``self.retry(countdown=retry_in)`` au lieu de
    tourner — la charge d'un tenant ne prive plus les autres. Sans
    ``company_id`` en kwarg, aucun scoping possible → exécute normalement.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            company_id = kwargs.get('company_id')
            ok, retry_in = consume(company_id, famille)
            if not ok:
                logger.info('tenant_ratelimit: report %s/%s (+%ss)',
                            company_id, famille, retry_in)
                raise self.retry(countdown=retry_in)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
