"""ENG3 — Garde-fous du moteur publicitaire.

RÈGLE PERMANENTE (extension de la règle #3 « les campagnes naissent PAUSED ») :
le moteur ne peut **JAMAIS** activer une campagne. L'activation n'est pas un
champ de ``GuardrailConfig`` et ``enforce()`` lève TOUJOURS sur une transition
vers un statut ACTIF — quelle que soit la config, sans aucun opt-in possible.

ENG9 étoffera ce module (plafond quotidien, ±variation hebdomadaire, détecteur
d'anomalie) ; ENG3 ne pose que l'invariant « jamais d'activation ».
"""
from __future__ import annotations

# Statuts considérés comme une ACTIVATION (interdite). On normalise en MAJUSCULES
# et on couvre le libellé Meta (``ACTIVE``) comme le français (``ACTIF``).
ACTIVE_STATUSES = frozenset({'ACTIVE', 'ACTIF'})


class GuardrailViolation(Exception):
    """Levée quand une action viole un garde-fou — elle n'est JAMAIS appliquée."""


def enforce(*, target_status, config=None):
    """Vérifie qu'une transition de statut de campagne est permise.

    Lève ``GuardrailViolation`` sur TOUTE transition vers un statut actif
    (``ACTIVE``/``ACTIF``), **indépendamment** de ``config`` : aucun réglage ne
    peut autoriser une activation par le moteur (invariant permanent). Renvoie
    ``True`` pour tout autre statut (``PAUSED``, etc.).

    ``config`` (``GuardrailConfig`` optionnel) est accepté pour une signature
    stable — il est délibérément IGNORÉ pour la règle d'activation ; ENG9 s'en
    servira pour les autres garde-fous (plafond, variation, anomalie).
    """
    normalized = str(target_status or '').strip().upper()
    if normalized in ACTIVE_STATUSES:
        raise GuardrailViolation(
            "Activation d'une campagne interdite : le moteur ne peut jamais "
            "activer une campagne (règle permanente — aucune configuration ne "
            "l'autorise)."
        )
    return True
