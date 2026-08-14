"""ARC28 — Manifeste plateforme du module CPQ (« déclarer une fois »).

Déclare ce que CPQ expose au hub KPI fédéré (ARC40, ``GET
/reporting/reports/kpi-federes/`` — « générateur de dashboard » existant,
aucun nouvel écran) :

* NTCPQ48 — délai moyen + p90 d'approbation de remise (NTCPQ7).

Les autres surfaces (recherche globale, chatter/records, champs perso,
import, agent, automatisations) restent HORS PÉRIMÈTRE de ce manifeste :
aucun modèle CPQ n'est aujourd'hui déclaré cherchable/chatterisé.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'cpq',
    'searchable_models': [],
    'record_targets': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    # NTCPQ48 — provider dotted, résolu par reporting.reports.kpi_federes.
    'kpi_providers': [
        'apps.cpq.selectors.kpi_delai_approbation',
    ],
}
