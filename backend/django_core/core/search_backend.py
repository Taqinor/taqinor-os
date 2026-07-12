"""NTPLT35 — Abstraction du moteur de recherche.

Interface stable ``SearchBackend`` (``index`` / ``delete`` / ``query``) qui
découple les apps du moteur physique. Deux implémentations :

* ``PostgresFtsBackend`` (DÉFAUT) — s'appuie sur le registre ``search_registry``
  (NTPLT31) et le FTS Postgres (NTPLT32-33). C'est le backend actif tant
  qu'aucun cluster externe n'est configuré : aucun coût, aucune dépendance.
* ``OpenSearchBackend`` — SQUELETTE strictement no-op sans ``OPENSEARCH_URL``.
  Sans la clé, ``get_search_backend()`` renvoie TOUJOURS le backend Postgres :
  clé absente = Postgres, zéro dépendance active, zéro coût. Le jour où un
  client à 100 M de lignes l'exige, on branche un cluster (GATED-founder) sans
  réécrire une seule app.

``core`` reste fondation : ce module n'importe aucune app métier. La requête
concrète (FTS vs icontains) vit dans ``apps/reporting/search.py`` (NTPLT33) ;
ici on ne pose que le CONTRAT + la sélection du backend par configuration.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class SearchBackend:
    """Contrat d'un moteur de recherche. Toute implémentation le respecte.

    * ``index(entity, obj)`` — (ré)indexe un objet. Pour le FTS Postgres c'est
      un no-op (le ``search_vector`` est maintenu par signaux/trigger côté DB).
    * ``delete(entity, obj_id)`` — retire un objet de l'index.
    * ``query(company, q, limit)`` — renvoie une liste de hits normalisés
      ``{'entity', 'id', 'label', 'route', 'rank'}`` scopés société.
    """

    name = 'base'

    def index(self, entity, obj):  # pragma: no cover - contrat
        raise NotImplementedError

    def delete(self, entity, obj_id):  # pragma: no cover - contrat
        raise NotImplementedError

    def query(self, company, q, limit=20):  # pragma: no cover - contrat
        raise NotImplementedError


class PostgresFtsBackend(SearchBackend):
    """Backend par défaut : délègue à ``apps/reporting/search.py`` (FTS/repli).

    ``index``/``delete`` sont des no-op : avec le FTS Postgres, le
    ``search_vector`` est maintenu PAR LA DB (signaux post_save NTPLT32), donc
    rien à pousser vers un index externe. ``query`` appelle la recherche
    globale existante via un import PARESSEUX (jamais au niveau module — ``core``
    ne dépend pas de ``reporting`` en dur).
    """

    name = 'postgres_fts'

    def index(self, entity, obj):
        return None

    def delete(self, entity, obj_id):
        return None

    def query(self, company, q, limit=20):
        # Résolution DYNAMIQUE (importlib) et non un ``import apps.reporting`` :
        # ``core`` est une couche de FONDATION qui ne doit référencer AUCUNE app
        # satellite (contrat import-linter ``core-foundation-is-a-base-layer``).
        # La délégation reste optionnelle — reporting absent → aucun résultat.
        import importlib
        try:
            reporting_search = importlib.import_module('apps.reporting.search')
        except Exception:  # noqa: BLE001 — reporting absent → aucun résultat
            logger.warning('search_backend: reporting.search indisponible')
            return []
        fn = getattr(reporting_search, 'global_search', None)
        if fn is None:
            return []
        return fn(company, q, limit=limit)


class OpenSearchBackend(SearchBackend):
    """SQUELETTE OpenSearch — strictement no-op sans ``OPENSEARCH_URL``.

    Aucune dépendance importée tant que la clé est absente. Le corps réel
    (client opensearch-py, mapping, bulk index) est GATED-founder : il ne sera
    écrit que le jour d'un déploiement cluster. En attendant, cette classe
    n'est JAMAIS sélectionnée par ``get_search_backend`` sans la clé.
    """

    name = 'opensearch'

    def __init__(self):
        self.url = getattr(settings, 'OPENSEARCH_URL', '') or ''

    def index(self, entity, obj):
        return None

    def delete(self, entity, obj_id):
        return None

    def query(self, company, q, limit=20):
        # Sans URL configurée, on dégrade proprement vers le backend Postgres.
        return PostgresFtsBackend().query(company, q, limit=limit)


# Cache du backend résolu (résolution une seule fois par process).
_BACKEND = None


def get_search_backend() -> SearchBackend:
    """Renvoie le backend actif selon la configuration.

    ``OPENSEARCH_URL`` présent ET non vide → ``OpenSearchBackend`` ; sinon
    ``PostgresFtsBackend`` (défaut absolu, zéro coût). Mémoïsé par process.
    """
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    url = getattr(settings, 'OPENSEARCH_URL', '') or ''
    _BACKEND = OpenSearchBackend() if url else PostgresFtsBackend()
    return _BACKEND


def reset_backend_cache():
    """Réinitialise le backend mémoïsé (test uniquement)."""
    global _BACKEND
    _BACKEND = None
