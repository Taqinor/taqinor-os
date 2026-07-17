"""Manifeste plateforme du module Assurances (voir ``core.platform``).

Déclare ce que le module Assurances expose aux surfaces transverses
(chatter/records, recherche, champs perso, import, agent, automations, KPI).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'assurances',
    # NTASS14 — cible de pièce jointe records.Attachment (constat amiable,
    # rapport d'expertise, photos de dégâts sur un sinistre). L'union
    # paresseuse de records.ALLOWED_TARGETS lit ce manifeste (ARC30) : aucun
    # besoin d'éditer apps/records/models.py.
    'record_targets': ['assurances.declarationsinistre'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
