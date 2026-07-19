"""PUB99 — Manifeste plateforme (ARC28) du moteur publicitaire.

Enregistre ``adsengine`` au registre ``core.platform`` : sans ce fichier, le
module était invisible de la recherche globale, du KPI fédéré (``reporting``) et
du chatbot (ARC33 ``agent_actions_module``). RÈGLE D'HONNÊTETÉ : on ne déclare
qu'une surface RÉELLEMENT câblée.

  * ``searchable_models`` — les campagnes miroir sont cherchables globalement
    (spec ``reporting.search._spec_campagne``, câblée dans le même lot) ;
  * ``kpi_providers`` — KPIs pub fédérés (dépense/leads 7 j) vers le dashboard
    central ``reporting`` (``selectors.kpi_publicite``) ;
  * ``agent_actions_module`` — 2-3 actions LECTURE SEULE pour le chatbot
    (dépense de la semaine, top ads, liste des campagnes). Les actions
    d'ÉCRITURE via chatbot restent HORS scope (décision fondateur gated).

Les surfaces non câblées (record_targets, customfields, dataimport,
automation_state_fields) restent volontairement vides.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'adsengine',
    'searchable_models': ['adsengine.adcampaignmirror'],
    'record_targets': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': 'apps.adsengine.agent_actions',
    'automation_state_fields': [],
    'kpi_providers': ['apps.adsengine.selectors.kpi_publicite'],
}
