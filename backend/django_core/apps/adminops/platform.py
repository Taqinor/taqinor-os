"""Manifeste plateforme du module `adminops` (NTADM5/17/36/48) — fournisseur
KPI « Santé & adoption » consommé par l'endpoint fédéré `reporting` (ARC40)."""
from __future__ import annotations

PLATFORM = {
    'module': 'adminops',
    'record_targets': [],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': ['apps.adminops.selectors.kpi_adminops'],
}
