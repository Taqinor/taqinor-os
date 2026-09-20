"""Manifeste plateforme du module Rapports (voir ``core.platform``).

Le reporting n'expose ni chatter, ni recherche, ni champ perso, ni import : il
LIT ce que les autres modules produisent. Son unique surface est donc
``kpi_providers``.

CAL218 — les indicateurs calepinage sont déclarés ICI, du côté qui les
CALCULE (``apps/reporting/calepinage_kpis.py``), pour qu'ils alimentent le KPI
fédéré qui existe déjà (``reports.kpi_federes``, ARC40) : aucun écran neuf,
aucune route neuve. Le provider se tait de lui-même quand le module calepinage
est désactivé pour la société, donc le gatage ``ModuleToggle`` est respecté
comme s'il était déclaré côté calepinage ; et ``core.platform.kpi_providers``
renvoyant un ENSEMBLE, une déclaration ultérieure du même chemin pointé côté
calepinage ne produirait aucun doublon.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'reporting',
    'record_targets': [],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': ['apps.reporting.calepinage_kpis.kpi_calepinage'],
}
