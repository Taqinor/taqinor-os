"""ARC28 — manifeste plateforme de l'app ``migration`` (déclaré une fois).

L'app ne branche aucune primitive transverse pour l'instant : son journal
d'import est celui de ``dataimport`` (``ImportJob``/``ImportJobRow``), jamais
un second. Le manifeste reste déclaré (vide) pour que l'app apparaisse dans le
recensement plateforme au lieu d'y être invisible.
"""

PLATFORM = {
    'module': 'migration',
    'record_targets': [],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
