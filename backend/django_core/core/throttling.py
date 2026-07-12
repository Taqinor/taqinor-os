"""NTPLT42 — throttle applicatif PAR TENANT (étend YAPIC12).

``TenantRateThrottle`` borne le débit de requêtes PAR SOCIÉTÉ : le script fou
d'UN client (une boucle qui martèle l'API) ne peut plus dégrader l'instance
partagée pour les AUTRES sociétés. Posé en ``DEFAULT_THROTTLE_CLASSES``, il
s'applique à toutes les vues DRF.

Budget : ``DEFAULT_THROTTLE_RATES['tenant']`` (settings, piloté par l'env
``TENANT_RATE_LIMIT``, défaut GÉNÉREUX ``1200/min``). ``0`` / valeur vide =
throttle DÉSACTIVÉ (``rate=None`` → ``allow_request`` laisse tout passer),
comportement historique.

Portée du compteur : la CLÉ de cache est la société (``company`` de l'appelant).
Une requête sans société résolue (anonyme, /token/, /register/, superuser sans
company) N'EST PAS throttlée par tenant (``get_cache_key`` renvoie ``None``) —
ces surfaces gardent leurs throttles dédiés (login/register par IP). Le 429
émis est l'exception DRF standard, donc uniformisé par l'enveloppe YAPIC12.
"""
from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class TenantRateThrottle(SimpleRateThrottle):
    """Débit par société (clé de cache = id de la company de l'appelant)."""

    scope = 'tenant'

    def get_cache_key(self, request, view):
        user = getattr(request, 'user', None)
        if user is None or not getattr(user, 'is_authenticated', False):
            return None  # anonyme → pas de throttle tenant (login/register gèrent)
        company = getattr(user, 'company', None)
        company_id = getattr(company, 'pk', None) if company is not None else None
        if company_id is None:
            return None  # superuser/opérateur sans société → non throttlé ici
        return f'throttle_tenant_{company_id}'
