"""Manifeste plateforme du module Assurances (voir ``core.platform``).

Déclare ce que le module Assurances expose aux surfaces transverses
(chatter/records, recherche, champs perso, import, agent, automations, KPI).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'assurances',
    'record_targets': [],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
