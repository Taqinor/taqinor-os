"""ARC28 — Manifeste plateforme du module crédit (« déclarer une fois »).

NTCRD43 — déclare ``LimiteCredit`` et ``DerogationCredit`` comme cibles du
chatter/records générique (``record_targets``) : leurs événements (changement
de limite NTCRD22, décision de dérogation) s'affichent dans le fil d'activité
unifié ``records`` sans chatter maison isolé.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'credit',
    'record_targets': [
        'credit.limitecredit',
        'credit.derogationcredit',
    ],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
