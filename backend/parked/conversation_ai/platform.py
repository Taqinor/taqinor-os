"""ARC28 — Manifeste plateforme du module « conversation_ai ».

RÈGLE D'HONNÊTETÉ : une surface n'est déclarée que si elle est RÉELLEMENT
câblée. Les enregistrements d'appels n'ont pour l'instant ni chatter, ni champs
personnalisés, ni import, ni actions agentiques : toutes les surfaces restent
vides tant que rien n'est câblé.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'conversation_ai',

    'searchable_models': [],
    'record_targets': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
