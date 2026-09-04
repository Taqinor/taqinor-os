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


#: SOL10 — le catalogue seedé porte des prix RÉELS **en MAD**.
PAYS_DES_PRIX_SEEDES = 'MA'


def seed_catalogue_hook(company, *, user=None):
    """Seede le catalogue simulateur de la nouvelle société (idempotent).

    SOL10 — RÈGLE CHECKED-FACTS (fondateur, absolue) : les prix de ce catalogue
    sont RÉELS et libellés **en MAD**. Pour un tenant dont le pays n'est PAS le
    Maroc, ils ne veulent rien dire et il n'existe AUCUNE source de prix pour sa
    devise : le hook ne seede alors AUCUN produit — jamais un prix converti,
    estimé ou « à ajuster ». La STRUCTURE (les catégories du catalogue solaire)
    lui est posée à part, par le gabarit de tenant
    (``authentication.tenant_templates``), et il renseigne ses propres prix.

    Comportement INCHANGÉ pour tout tenant marocain — c'est-à-dire pour toutes
    les sociétés existantes (``Company.pays`` vaut ``MA`` par défaut, SOL8).

    Best-effort : encapsulé par ``run_signup_hooks`` (un échec est isolé et
    n'empêche jamais la création de la société ni les autres hooks)."""
    pays = (getattr(company, 'pays', PAYS_DES_PRIX_SEEDES)
            or PAYS_DES_PRIX_SEEDES).upper()
    if pays != PAYS_DES_PRIX_SEEDES:
        logger.info(
            'catalogue non seedé pour %s (pays %s) : les prix du catalogue '
            'sont en MAD et aucun prix ne doit être inventé (SOL10).',
            company.slug, pays)
        return
    from django.core.management import call_command
    call_command('seed_catalogue', company_slug=company.slug, verbosity=0)


def register_stock_signup_hooks():
    """Branche le hook catalogue au registre (idempotent)."""
    from core.signup_hooks import register_signup_hook
    register_signup_hook('catalogue', seed_catalogue_hook, priority=50)
