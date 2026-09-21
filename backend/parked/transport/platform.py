"""ARC28 — Manifeste plateforme du module Transport (« déclarer une fois »).

`record_targets` déclare les cibles chatter/pièces jointes (ARC8/ARC26) :
`OrdreTransport` reçoit le chatter générique (`ChatterViewSetMixin`, NTLOG8),
`EtapeTransport` reçoit les photos/signatures de la preuve de livraison
(NTLOG9), `ReserveReception` ses photos de réserve (NTLOG18) — toutes via
`records.Attachment`/`records.Activity` génériques. Sans cette déclaration,
`records.ALLOWED_TARGETS`/`records.Attachment` refusent ces cibles
(« Type de cible non autorisé »).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'transport',
    'record_targets': [
        'transport.ordretransport',
        'transport.etapetransport',
        'transport.reservereception',
    ],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
