"""ARC28 — Manifeste plateforme du module « ai_governance ».

RÈGLE D'HONNÊTETÉ : une surface n'est déclarée que si elle est RÉELLEMENT
câblée. Les copilotes NTAI sont des endpoints de génération (aucun objet
métier propre, aucun chatter, aucun champ personnalisé), donc toutes les
surfaces restent vides tant que rien n'est câblé.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'ai_governance',

    'searchable_models': [],
    'record_targets': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
