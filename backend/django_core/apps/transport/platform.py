"""ARC28 — Manifeste plateforme du module Transport (« déclarer une fois »).

`record_targets` déclare les cibles chatter/pièces jointes (ARC8/ARC26) :
`OrdreTransport` reçoit le chatter générique (`ChatterViewSetMixin`, NTLOG8).
Sans cette déclaration, `records.ALLOWED_TARGETS` refuse cette cible
(« Type de cible non autorisé »).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'transport',
    'record_targets': [
        'transport.ordretransport',
    ],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
