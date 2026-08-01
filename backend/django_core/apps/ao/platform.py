"""ARC28/ARC30 — Manifeste plateforme du module Appels d'offres
(« déclarer une fois »).

Déclare ce que AO expose aux surfaces transverses (voir ``core.platform``).
ARC30 fait basculer la source de ``records.ALLOWED_TARGETS`` d'un ``set``
littéral figé vers l'union paresseuse des manifestes ``record_targets`` — ce
manifeste porte la cible chatter/records historique (``ao.appeloffre``, ARC26
— pièces jointes génériques).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'ao',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['ao.appeloffre'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    # AOF15/ARC34 — le statut d'un AO est automatisable par une règle no-code
    # ``RECORD_STATE_CHANGE``. La surface est RÉELLEMENT câblée (règle
    # d'honnêteté ARC41) : ``apps.ao.services.changer_statut_ao`` — le SEUL
    # point de mutation du statut — appelle
    # ``emettre_changement_statut_automation`` après chaque transition réussie,
    # sur le même précédent que ``contrats``/``gestion_projet``. Le statut visé
    # est celui du DOMAINE AO, jamais une étape STAGES.py (règle #2).
    'automation_state_fields': [
        {'model': 'ao.appeloffre', 'field': 'statut'},
    ],
    'kpi_providers': [],
}
