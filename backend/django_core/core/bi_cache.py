"""NTDATA36 — pré-agrégation / cache des widgets BI lourds (Redis, TTL).

Couche de FONDATION : mémorise le résultat d'un ``data_explorer.run_query`` par
``(société, dataset, spec complète — filtres compris, utilisateur)`` pour qu'un
dashboard lourd se recharge en sub-seconde. Aucune app métier n'est importée ;
le backend de cache est celui de Django (Redis en compose, LocMem en test) via
``core.cache``, dont les clés sont DÉJÀ préfixées par société — deux tenants ne
peuvent physiquement pas partager une entrée.

Deux règles de sûreté, dans cet ordre :

1. **Rien n'est mis en cache sans demande explicite.** La pré-agrégation est
   OPT-IN par widget (``"cache": true`` ou ``"cache_ttl": 900`` dans le
   ``layout``) : on met en cache ce qui est LOURD, pas tout — un chiffre qui
   doit être frais reste frais.
2. **Aucune fuite entre utilisateurs.** Par défaut la clé INCLUT l'utilisateur,
   parce qu'un dataset peut masquer des champs selon les droits (prix d'achat,
   périmètre d'un commercial). Un dataset ne partage son entrée entre les
   utilisateurs d'une société que s'il le DÉCLARE explicitement à
   l'enregistrement (``register_dataset(..., cache_partage=True)``).

L'invalidation est celle du TTL (concept « pre-aggregation » de Cube) : pas de
graphe de dépendances à maintenir, donc pas de cache qui ment en silence.
"""
from __future__ import annotations

import hashlib
import json
import logging

from django.conf import settings

from . import cache as tenant_cache
from . import data_explorer

logger = logging.getLogger(__name__)

#: TTL par défaut (secondes) quand un widget demande le cache sans en préciser un.
TTL_DEFAUT = 300
#: Borne dure : un widget ne peut pas geler un chiffre plus d'une heure.
TTL_MAX = 3600


def ttl_effectif(demande=None) -> int:
    """TTL retenu, borné. ``0`` (ou négatif) = pas de cache."""
    if demande is None:
        demande = getattr(settings, 'BI_WIDGET_CACHE_TTL', TTL_DEFAUT)
    try:
        ttl = int(demande)
    except (TypeError, ValueError):
        ttl = TTL_DEFAUT
    if ttl <= 0:
        return 0
    return min(ttl, TTL_MAX)


def _empreinte(dataset, spec) -> str:
    """Empreinte stable de la requête (dataset + spec, filtres compris)."""
    charge = json.dumps({'dataset': dataset, 'spec': spec or {}},
                        sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(charge.encode('utf-8')).hexdigest()[:32]


def cle_cache(dataset, spec, user, *, partage=False) -> str:
    """Nom de clé (le préfixe société est ajouté par ``core.cache``).

    Sans ``partage``, l'identifiant utilisateur entre dans la clé : un dataset
    qui masque des champs selon les droits ne peut jamais servir à un
    utilisateur le résultat calculé pour un autre.
    """
    suffixe = ''
    if not partage:
        suffixe = f':u{getattr(user, "pk", None)}'
    return f'bi:{dataset}:{_empreinte(dataset, spec)}{suffixe}'


def _partage(dataset) -> bool:
    try:
        return bool(data_explorer.get_dataset(dataset).get('cache_partage'))
    except data_explorer.DatasetInconnu:
        return False


def run_query_cache(dataset, company, user, spec, ttl=None):
    """``run_query`` mémoïsé. Renvoie ``(rows, statut)``.

    ``statut`` ∈ ``{'hit', 'miss', ''}`` — ``''`` quand le cache est désactivé
    (TTL nul). Un backend de cache indisponible dégrade en calcul direct :
    ``core.cache`` avale ses propres pannes, jamais l'appelant.
    """
    ttl = ttl_effectif(ttl)
    if not ttl:
        return data_explorer.run_query(dataset, company, user, spec), ''
    company_id = getattr(company, 'pk', None)
    nom = cle_cache(dataset, spec, user, partage=_partage(dataset))
    memorise = tenant_cache.get(company_id, nom)
    if memorise is not None:
        logger.info('cache BI HIT société=%s dataset=%s', company_id, dataset)
        return memorise, 'hit'
    rows = data_explorer.run_query(dataset, company, user, spec)
    tenant_cache.set(company_id, nom, rows, ttl)
    logger.info('cache BI MISS société=%s dataset=%s (ttl=%ss)',
                company_id, dataset, ttl)
    return rows, 'miss'


def ttl_du_widget(widget):
    """TTL demandé par un widget de ``Dashboard.layout``.

    ``None`` = le widget ne demande PAS le cache (défaut : chiffre frais).
    ``{"cache": true}`` = TTL par défaut ; ``{"cache_ttl": 900}`` = TTL choisi.
    """
    if not isinstance(widget, dict):
        return None
    if 'cache_ttl' in widget:
        return ttl_effectif(widget.get('cache_ttl'))
    if widget.get('cache'):
        return ttl_effectif(None)
    return None
