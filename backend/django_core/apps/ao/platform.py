"""ARC28/ARC30 — Manifeste plateforme du module Appels d'offres
(« déclarer une fois »).

Déclare ce que AO expose aux surfaces transverses (voir ``core.platform``).
ARC30 fait basculer la source de ``records.ALLOWED_TARGETS`` d'un ``set``
littéral figé vers l'union paresseuse des manifestes ``record_targets`` — ce
manifeste porte la cible chatter/records historique (``ao.appeloffre``, ARC26
— pièces jointes génériques).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'ao',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['ao.appeloffre'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
