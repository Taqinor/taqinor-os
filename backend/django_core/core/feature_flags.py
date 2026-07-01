"""FG391 — Flags de fonctionnalités / modules par tenant (services).

Couche de FONDATION : décide si un module est actif POUR UNE SOCIÉTÉ à partir de
la table ``ModuleToggle``. ``core`` ne connaît AUCUN module métier (contrat
import-linter ``core-foundation-is-a-base-layer``) : ``module`` est une clé libre
fournie par l'appelant. Politique : ACTIVÉ PAR DÉFAUT (l'absence de ligne ⇒
actif) ; une ligne ``actif=False`` désactive le module pour la société.
"""
from __future__ import annotations


def module_actif(company, module, *, defaut=True):
    """Vrai si ``module`` est actif pour ``company``.

    Sans ligne ``ModuleToggle`` → ``defaut`` (activé par défaut). Avec ligne →
    son champ ``actif``. ``company`` ``None`` → ``defaut`` (pas de scope).
    """
    if company is None:
        return defaut
    from .models import ModuleToggle
    toggle = (ModuleToggle.objects
              .filter(company=company, module=module)
              .values_list('actif', flat=True)
              .first())
    return defaut if toggle is None else bool(toggle)


def modules_desactives(company):
    """Ensemble des clés de modules explicitement désactivés pour la société."""
    if company is None:
        return set()
    from .models import ModuleToggle
    return set(
        ModuleToggle.objects
        .filter(company=company, actif=False)
        .values_list('module', flat=True)
    )
