"""Manifeste plateforme du module BTP Chantier (ARC28/ARC30 — « déclarer une fois »).

Déclare les cibles chatter/pièces jointes (``records.ALLOWED_TARGETS``) pour
``ReserveChantier`` (NTCON1/2 — photos avant/après de levée) et
``JournalChantier`` (NTCON6 — photos du journal quotidien).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'btp_chantier',
    'record_targets': [
        'btp_chantier.reservechantier',
        'btp_chantier.journalchantier',
    ],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
