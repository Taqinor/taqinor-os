"""SCA20 — Hook de seed catalogue « à la création d'une société ».

Le signup ne seedait JAMAIS le catalogue produit : une nouvelle société démarrait
sans aucun produit du simulateur. Ce hook appelle la commande idempotente et
additive ``seed_catalogue`` pour la société fraîchement créée (mêmes garanties :
ne touche jamais un prix/une quantité existants, additif uniquement).

Enregistré dans ``core.signup_hooks`` depuis ``apps/stock/apps.py`` ``ready()``
(motif du bus M6 : la vue de signup ne connaît pas cet abonné).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def seed_catalogue_hook(company, *, user=None):
    """Seede le catalogue simulateur de la nouvelle société (idempotent).

    Best-effort : encapsulé par ``run_signup_hooks`` (un échec est isolé et
    n'empêche jamais la création de la société ni les autres hooks)."""
    from django.core.management import call_command
    call_command('seed_catalogue', company_slug=company.slug, verbosity=0)


def register_stock_signup_hooks():
    """Branche le hook catalogue au registre (idempotent)."""
    from core.signup_hooks import register_signup_hook
    register_signup_hook('catalogue', seed_catalogue_hook, priority=50)
