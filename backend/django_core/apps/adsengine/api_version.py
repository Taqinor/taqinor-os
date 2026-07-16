"""ADSENG2 — Version de l'API Meta (Graph / Marketing / Conversions), SOURCE
UNIQUE, plain-constant.

Ce module ne contient QUE des constantes — aucun modèle, aucun import d'app
métier, aucune dépendance lourde (pas httpx). Il est donc importable de PARTOUT
sans risque de cycle ni d'infraction import-linter : le client Meta
(``adsengine.meta_client``) ET l'émetteur CAPI côté ``apps.ventes`` s'y réfèrent,
pour qu'une version qui expire ne soit plus jamais codée en dur à deux endroits
divergents (v19.0 était morte depuis 02/2025 dans l'émetteur, alors que le
client était déjà en v25 — exactement la dérive que cette source unique
supprime).

Mise à jour de version : changer la valeur ICI, une seule fois.
"""
from __future__ import annotations

# Version courante de l'API Graph/Marketing/Conversions (recherche 16/07 : v25).
GRAPH_VERSION = 'v25.0'

# Base d'URL Graph (sans l'objet ni le endpoint — l'appelant les concatène).
GRAPH_BASE_URL = f'https://graph.facebook.com/{GRAPH_VERSION}'
