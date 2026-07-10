"""ARC28/ARC30 — Manifeste plateforme du module RH (« déclarer une fois »).

Déclare ce que RH expose aux surfaces transverses (voir ``core.platform``).
ARC30 fait basculer la source de ``records.ALLOWED_TARGETS`` d'un ``set``
littéral figé vers l'union paresseuse des manifestes ``record_targets`` — ce
manifeste porte la cible chatter/records historique (``rh.dossieremploye``).
Les autres surfaces restent vides ici (hors périmètre ARC30).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'rh',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['rh.dossieremploye'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
