"""ARC23 — Hooks de seed « à la création d'une société » côté Paramètres.

Le signup d'une nouvelle société doit initialiser ses référentiels Paramètres.
Chaque hook est idempotent (rejouable sans doublon) et enregistré dans
``core.signup_hooks`` depuis ``apps/parametres/apps.py`` ``ready()`` (motif du
bus M6 : la vue de signup ne connaît pas cet abonné).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def seed_taux_tva_hook(company, *, user=None):
    """Seede les taux de TVA marocains usuels de la société (idempotent).

    Best-effort : encapsulé par ``run_signup_hooks`` (un échec est isolé et
    n'empêche jamais la création de la société ni les autres hooks)."""
    from .models_taxes import TauxTVA
    TauxTVA.seed_defaults(company)


def seed_unites_mesure_hook(company, *, user=None):
    """Seede les unités de mesure usuelles de la société (idempotent)."""
    from .models_units import UniteMesure
    UniteMesure.seed_defaults(company)


def register_parametres_signup_hooks():
    """Branche les hooks de seed Paramètres au registre (idempotent)."""
    from core.signup_hooks import register_signup_hook
    register_signup_hook('taux_tva', seed_taux_tva_hook, priority=30)
    register_signup_hook('unites_mesure', seed_unites_mesure_hook,
                         priority=30)
