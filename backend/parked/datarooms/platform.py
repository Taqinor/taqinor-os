"""ARC28 — manifeste plateforme du module ``datarooms`` (déclaré une fois).

RÈGLE D'HONNÊTETÉ : une surface n'est déclarée QUE si elle est réellement
câblée. Les surfaces non branchées restent vides plutôt que de mentir à la
matrice de couverture (``core.platform_coverage``).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'datarooms',
    'record_targets': [],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
