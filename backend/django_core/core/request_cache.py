"""NTPLT16 (pilote SCA43) — cache de configuration PAR REQUÊTE (contextvar).

Un petit mémo à durée de vie d'UNE requête HTTP, pour mutualiser les lectures de
configuration société (``CompanyProfile``, ``DocumentTemplates``, identité,
conditions de paiement, taux de TVA société) que les ACCESSEURS consomment. Le
moteur de devis (``quote_engine``) reste intact : il rend, il ne change rien
(RÈGLE #4). Le cache vit strictement EN AMONT du moteur, au niveau des accesseurs
de config, et il est invalidé À CHAQUE requête (réinitialisation du contextvar).

Pourquoi : la liste des devis appelle le moteur (``build_quote_data``) UNE FOIS
PAR DEVIS pour le total d'affichage ; chaque appel refaisait ~6 requêtes de
config identiques pour la MÊME société → N+1 réel (~38-109 requêtes). Comme la
config d'une société est constante le temps d'une requête, on la lit une fois et
on la mémorise pour les appels suivants de la même requête.

Portée & sûreté
---------------
* ``contextvar`` : chaque requête (thread/async) a son propre mémo, aucune fuite
  entre requêtes ni entre tenants (la clé porte l'``id`` société).
* HORS requête (tâche Celery, rendu PDF asynchrone, shell, tests unitaires sans
  ``request_scope``) → AUCUN scope actif → ``memoize`` appelle simplement le
  producteur à chaque fois : comportement STRICTEMENT identique à aujourd'hui
  (cache désactivé), donc le rendu reste bit-identique.
* Ce module NE DÉPEND DE RIEN (couche fondation ``core``, contrat import-linter :
  ``core`` ne doit jamais importer une app domaine/satellite).

Usage
-----
    from core import request_cache

    # accesseur de config :
    profil = request_cache.memoize(("company_profile", company_id),
                                   lambda: CompanyProfile.get(company=company))

    # entrée/sortie du scope (fait par le middleware, jamais à la main ailleurs) :
    with request_cache.request_scope():
        ...  # tout appel à memoize pendant ce bloc partage un seul mémo
"""
from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Callable, Hashable, Optional

# Le mémo courant : un dict {clé_hashable: valeur} quand une requête est en cours,
# ``None`` en dehors de toute requête (cache désactivé → comportement historique).
_CACHE: "contextvars.ContextVar[Optional[dict]]" = contextvars.ContextVar(
    "taqinor_request_config_cache", default=None
)


def is_active() -> bool:
    """Vrai si un scope de requête est actif (mémo disponible)."""
    return _CACHE.get() is not None


def memoize(key: Hashable, producer: Callable[[], Any]) -> Any:
    """Retourne ``producer()``, mémorisé sous ``key`` pour la requête courante.

    - Scope actif : première fois → calcule + stocke ; ensuite → renvoie le
      stocké (0 requête SQL supplémentaire).
    - Aucun scope actif (hors requête) : appelle ``producer()`` à chaque fois,
      exactement comme sans cache (comportement historique préservé).

    La ``key`` DOIT porter l'identité société (id) pour éviter toute fuite
    multi-tenant. Une valeur ``None`` produite est mémorisée telle quelle (elle
    représente « pas de profil » — un repli légitime, pas une absence de calcul).
    """
    cache = _CACHE.get()
    if cache is None:
        # Hors requête : pas de mémorisation, on recalcule à chaque fois.
        return producer()
    # Sentinelle pour distinguer « absent » d'une vraie valeur ``None`` mémorisée.
    marker = _MISSING
    value = cache.get(key, marker)
    if value is marker:
        value = producer()
        cache[key] = value
    return value


class _Missing:
    __slots__ = ()


_MISSING = _Missing()


@contextlib.contextmanager
def request_scope():
    """Ouvre un mémo de config neuf pour la durée du bloc, puis le retire.

    Réentrant sans risque : on pose TOUJOURS un dict frais à l'entrée et on
    restaure l'état précédent à la sortie (le contextvar est remis à sa valeur
    d'avant via le token). Deux requêtes concurrentes ont des contextes séparés,
    donc des mémos séparés.
    """
    token = _CACHE.set({})
    try:
        yield
    finally:
        _CACHE.reset(token)


class RequestConfigCacheMiddleware:
    """Ouvre un ``request_scope`` autour de chaque requête HTTP.

    Effet : pendant le traitement d'UNE requête, les accesseurs de config qui
    passent par ``memoize`` partagent un seul mémo → la config société est lue
    une seule fois quel que soit le nombre de devis sérialisés. Aucun coût hors
    de ce partage (un ``dict`` vide posé/retiré), aucune écriture, aucune requête.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with request_scope():
            return self.get_response(request)
