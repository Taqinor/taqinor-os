"""Manifeste plateforme du module ESG (ARC28/ARC30 — « déclarer une fois »).

Déclare la cible chatter/pièces jointes (``records.ALLOWED_TARGETS``) pour
``DocumentPolitiqueESG`` (NTESG13 — dépôt des politiques RSE via
``records.Attachment``, jamais un ``FileField`` propre à l'app).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'esg',
    'record_targets': [
        'esg.documentpolitiqueesg',
    ],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
