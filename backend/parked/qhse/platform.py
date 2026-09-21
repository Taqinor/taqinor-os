"""ARC28/ARC30 — Manifeste plateforme du module QHSE (« déclarer une fois »).

Déclare ce que QHSE expose aux surfaces transverses (voir ``core.platform``).
ARC30 fait basculer la source de ``records.ALLOWED_TARGETS`` d'un ``set``
littéral figé vers l'union paresseuse des manifestes ``record_targets`` — ce
manifeste porte les 2 cibles chatter/records historiques (QHSE8 : photos de
contrôle sur un relevé ITP, pièces jointes d'une non-conformité).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'qhse',
    # ARC30 — cibles chatter/records historiques (records.ALLOWED_TARGETS).
    'record_targets': ['qhse.relevecontrole', 'qhse.nonconformite'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
