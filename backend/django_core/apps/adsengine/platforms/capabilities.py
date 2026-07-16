"""ADSENG49 — Matrice de capacités plateforme, comme DONNÉES (pas de la logique).

Un dict de module (style ``STAGES.py`` / ``rules.RULE_TEMPLATES``) décrit CHAQUE
plateforme : crée-t-elle en PAUSED par défaut, budget minimum, granularité des
insights, split-test natif. La matrice **pilote les gardes** : une plateforme
SANS ``paused_by_default`` ⇒ la garde impose au client de FORCER PAUSED avant
toute création (défense de la règle #3 au-delà de Meta).

Aujourd'hui SEULE Meta est construite (paused-par-défaut confirmé). Les
plateformes GATED (google/snapchat/tiktok — budget/produit) NE SONT PAS ici :
une plateforme ABSENTE de la matrice résout sur le **défaut prudent**
(``paused_by_default=False``) ⇒ la garde force PAUSED. Ajouter une plateforme se
fait en éditant CES DONNÉES, jamais un ``if platform == …`` dans le code.
"""
from __future__ import annotations

import copy

# Granularité de reporting des insights (agnostique).
GRANULARITY_AD = 'ad'
GRANULARITY_ASSET = 'asset'


# ── La MATRICE (données). Une entrée par plateforme construite. ───────────────
CAPABILITIES = {
    'meta': {
        'platform': 'meta',
        # Meta : toute création naît PAUSED (forcé en dur par meta_client) →
        # paused-par-défaut CONFIRMÉ.
        'paused_by_default': True,
        # Budget minimum d'un ad set (MAD/jour) — garde-fou prudent.
        'min_daily_budget_mad': 10,
        # Reporting au niveau ad (la granularité asset/DCO est une inconnue
        # terrain FT4 — cf. field_tests).
        'insight_granularity': GRANULARITY_AD,
        'supports_split_test': True,
    },
}

# Défaut PRUDENT pour toute plateforme non listée : PAS de paused-par-défaut ⇒
# la garde force PAUSED côté client (jamais un chemin ACTIVE implicite).
DEFAULT_CAPABILITIES = {
    'platform': 'unknown',
    'paused_by_default': False,
    'min_daily_budget_mad': None,
    'insight_granularity': GRANULARITY_AD,
    'supports_split_test': False,
}


def capabilities_for(platform):
    """Capacités d'une plateforme (copie profonde). Une plateforme inconnue
    résout sur le défaut prudent (paused-par-défaut FALSE)."""
    entry = CAPABILITIES.get(platform)
    if entry is None:
        fallback = copy.deepcopy(DEFAULT_CAPABILITIES)
        fallback['platform'] = platform
        return fallback
    return copy.deepcopy(entry)


def paused_by_default(platform):
    """Vrai si la plateforme crée en PAUSED par défaut (Meta : oui)."""
    return bool(capabilities_for(platform).get('paused_by_default'))


def requires_forced_paused(platform):
    """LA GARDE (pilotée par les données) : une plateforme SANS paused-par-défaut
    ⇒ le client DOIT forcer PAUSED avant toute création. Renvoie ``True`` quand
    ce forçage explicite est requis (Meta : ``False`` — elle force déjà)."""
    return not paused_by_default(platform)


def min_daily_budget_mad(platform):
    """Budget quotidien minimum d'un ad set sur la plateforme (``None`` si
    inconnu)."""
    return capabilities_for(platform).get('min_daily_budget_mad')


def insight_granularity(platform):
    """Granularité de reporting des insights (``ad`` / ``asset``)."""
    return capabilities_for(platform).get('insight_granularity')


def known_platforms():
    """Plateformes réellement construites (présentes dans la matrice)."""
    return sorted(CAPABILITIES)
