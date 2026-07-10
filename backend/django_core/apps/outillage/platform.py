"""ARC28/ARC30 — Manifeste plateforme du module Outillage (« déclarer une fois »).

Déclare ce que Outillage expose aux surfaces transverses (voir
``core.platform``). ARC30 fait basculer la source de
``records.ALLOWED_TARGETS`` d'un ``set`` littéral figé vers l'union paresseuse
des manifestes ``record_targets`` — ce manifeste porte la cible chatter/records
historique (``outillage.outillage``).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'outillage',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['outillage.outillage'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
