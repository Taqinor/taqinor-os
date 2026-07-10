"""ARC28/ARC30 — Manifeste plateforme du module Flotte (« déclarer une fois »).

Déclare ce que Flotte expose aux surfaces transverses (voir ``core.platform``).
ARC30 fait basculer la source de ``records.ALLOWED_TARGETS`` d'un ``set``
littéral figé vers l'union paresseuse des manifestes ``record_targets`` — ce
manifeste porte la cible chatter/records historique (``flotte.vehicule``,
ARC8 — le véhicule reçoit le chatter générique via ChatterViewSetMixin, son
journal maison ``ActiviteFlotte`` reste intact en parallèle).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'flotte',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['flotte.vehicule'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
