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

import datetime

# Version courante de l'API Graph/Marketing/Conversions (recherche 16/07 : v25).
GRAPH_VERSION = 'v25.0'

# Base d'URL Graph (sans l'objet ni le endpoint — l'appelant les concatène).
GRAPH_BASE_URL = f'https://graph.facebook.com/{GRAPH_VERSION}'

# ── PUB102 — Vigie d'EOL (fin de vie) ────────────────────────────────────────
# Meta déprécie chaque version ~2 ans après sa sortie. On matérialise ces deux
# repères (approximatifs, ajustables à la main comme GRAPH_VERSION) pour qu'une
# vigie périodique alerte AVANT l'EOL — la dérive v19 (morte depuis 02/2025)
# qui a motivé ce module ne doit plus se reproduire. On n'AUTO-BUMP JAMAIS : la
# montée de version reste un geste humain (changer GRAPH_VERSION ici).
GRAPH_VERSION_RELEASED = datetime.date(2025, 7, 1)   # v25.0 (approx.)
GRAPH_VERSION_EOL_MONTHS = 24                          # cycle Meta ≈ 2 ans


def graph_version_eol_date():
    """Date approximative d'EOL de la version courante (sortie + ~24 mois)."""
    released = GRAPH_VERSION_RELEASED
    # Index de mois 0-based, puis retour en 1-based pour ``datetime.date``.
    idx = (released.year * 12 + (released.month - 1)) + GRAPH_VERSION_EOL_MONTHS
    year, month0 = divmod(idx, 12)
    day = min(released.day, 28)  # jamais un 31 février
    return datetime.date(year, month0 + 1, day)


def months_until_graph_eol(today=None):
    """Nombre (entier, arrondi au plancher) de mois avant l'EOL de la version
    courante. Négatif si l'EOL est déjà passée. Fonction PURE (testable en
    injectant ``today``)."""
    today = today or datetime.date.today()
    eol = graph_version_eol_date()
    months = (eol.year - today.year) * 12 + (eol.month - today.month)
    if eol.day < today.day:
        months -= 1
    return months
