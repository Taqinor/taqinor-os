"""CAD40 — hook de seed « à la création d'une société » : les jours fériés.

Constat de l'audit L3 du 21/09/2026 : aucun crochet de création de société ne
posait de férié (``apps/parametres/signup_hooks.py``, ``apps/stock/
signup_hooks.py``, ``authentication/signup_seeds.py``), et ``is_jour_ouvre``
ne bloque un jour QUE s'il existe une ligne ``Holiday``. Une société neuve
n'avait donc aucun férié : une touche de cadence pouvait tomber le 1ᵉʳ Mai
comme le jour de l'Aïd.

Les fériés arrivent désormais à la création, comme la TVA et les unités de
mesure : les 9 fixes, PLUS les fêtes mobiles que ``core.calendar`` connaît
pour l'année en cours. **Rien n'est calculé** — une année dont les dates
lunaires ne sont pas connues n'en reçoit aucune, et le rappel de
``calendar_utils.rappel_fetes_mobiles`` le dit à l'écran.

Même patron que les autres hooks : idempotent (``get_or_create``), additif,
rejouable sans doublon.
"""
from __future__ import annotations


def seed_jours_feries(company, *, user=None):
    """Fériés fixes + fêtes mobiles connues de l'année — idempotent."""
    from .management.commands.seed_ma_holidays import (
        seed_holidays_for_company,
    )
    seed_holidays_for_company(company)


def register_notifications_signup_hooks():
    """Branche le hook de seed au registre (idempotent)."""
    from core.signup_hooks import register_signup_hook
    register_signup_hook('jours_feries', seed_jours_feries, priority=20)
