"""NTAPI1 — résolution de la version d'API DEMANDÉE par un appel public.

Deux notions DISTINCTES, volontairement non fusionnées :

* la version **demandée** (ce module) — lue depuis le CHEMIN
  (``/api/public/v1/…``) et, à défaut, depuis l'en-tête de requête
  ``X-Taqinor-Api-Version``. C'est elle qui dit quel CONTRAT le client croit
  appeler : elle sert à cibler les annonces de dépréciation (NTAPI2) sans
  jamais dépendre de la clé ;
* la version **servie** (NTAPI5, ``ApiKey.api_version``) — épinglée par clé,
  renvoyée sur chaque réponse dans ``X-Taqinor-Api-Version``. Changer
  d'épinglage reste une action admin explicite.

Les deux coexistent : une clé épinglée ``v2`` appelant ``/api/public/v1/…``
DEMANDE v1 et se voit SERVIR ce que son épinglage dit — le contrat NTAPI5 est
inchangé, NTAPI1 n'ajoute qu'une lecture supplémentaire.
"""
from __future__ import annotations

import re

from .constants import (
    PUBLIC_API_DEFAULT_VERSION,
    PUBLIC_API_LEGACY_BASE,
    PUBLIC_API_VERSIONS,
)

# En-tête de REQUÊTE (fallback) — même nom que l'en-tête de réponse NTAPI5,
# côté client : « je veux la v1 » / « je sers la v1 ».
REQUEST_VERSION_HEADER = 'HTTP_X_TAQINOR_API_VERSION'

# `/api/public/<version>/…` — la version est le premier segment APRÈS la
# racine publique. Construit depuis les constantes : ajouter 'v2' à
# `PUBLIC_API_VERSIONS` suffit, aucune regex à retoucher.
_VERSION_IN_PATH_RE = re.compile(
    r'^{base}(?P<version>{versions})(?:/|$)'.format(
        base=re.escape(PUBLIC_API_LEGACY_BASE),
        versions='|'.join(re.escape(v) for v in PUBLIC_API_VERSIONS),
    )
)


def version_depuis_chemin(path):
    """Version lue dans le CHEMIN, ou ``None`` si le chemin n'en porte pas.

    Ne renvoie JAMAIS une version inconnue : un ``/api/public/v9/…`` n'est pas
    monté (404 par le routeur) et ne doit pas non plus être « résolu » ici.
    """
    if not path:
        return None
    match = _VERSION_IN_PATH_RE.match(path)
    return match.group('version') if match else None


def version_depuis_entete(meta):
    """Version lue dans l'en-tête de requête ``X-Taqinor-Api-Version``.

    Une valeur inconnue est IGNORÉE (``None``) plutôt que propagée : l'en-tête
    est un simple repli de confort, jamais un moyen d'atteindre un contrat non
    monté.
    """
    raw = (meta or {}).get(REQUEST_VERSION_HEADER)
    if not raw:
        return None
    value = str(raw).strip().lower()
    return value if value in PUBLIC_API_VERSIONS else None


def version_demandee(request):
    """Version demandée par CET appel : chemin, puis en-tête, puis défaut."""
    path = getattr(request, 'path', '') or ''
    meta = getattr(request, 'META', None) or {}
    return (version_depuis_chemin(path)
            or version_depuis_entete(meta)
            or PUBLIC_API_DEFAULT_VERSION)
