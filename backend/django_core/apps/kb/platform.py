"""ARC28/ARC30 — Manifeste plateforme du module KB (« déclarer une fois »).

Déclare ce que la base de connaissances expose aux surfaces transverses (voir
``core.platform``). ARC30 fait basculer la source de
``records.ALLOWED_TARGETS`` d'un ``set`` littéral figé vers l'union paresseuse
des manifestes ``record_targets`` — ce manifeste porte la cible chatter/records
historique (``kb.kbarticle`` — XKB10 pièces jointes/images, XKB13 commentaires
génériques réutilisant la même entrée).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'kb',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['kb.kbarticle'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
