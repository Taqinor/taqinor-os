"""ARC28 — Manifeste plateforme du module MRP (« déclarer une fois »).

`record_targets` déclare la cible chatter (ARC8) : `OrdreFabrication` reçoit
le chatter générique (`ChatterViewSetMixin`, NTMFG38) — historique automatique
des transitions de statut + notes manuelles, via `records.Activity`
générique. Sans cette déclaration, la surface générique `records`
(`ALLOWED_TARGETS`) refuse cette cible pour tout futur usage passant par
elle (ex. `records.Attachment` si l'OF gagne des pièces jointes plus tard) —
même motif que `apps/transport/platform.py`.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'mrp',
    'record_targets': [
        'mrp.ordrefabrication',
    ],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
