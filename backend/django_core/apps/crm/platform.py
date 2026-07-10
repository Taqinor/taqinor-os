"""ARC28 — Manifeste plateforme du module CRM (« déclarer une fois »).

Déclare ce que le CRM expose aux surfaces transverses (voir ``core.platform``).
Ce manifeste ne CÂBLE rien lui-même : il décrit, en métadonnées, ce que les
surfaces (recherche, chatter/records, champs perso, import/export, actions agent,
automatisations, KPI) liront à la place de leurs listes hard-codées (bascule dans
ARC29-34). Il reflète le câblage CRM RÉEL d'aujourd'hui :

* recherche globale (``reporting/search.py``) : Leads + Clients ;
* cibles chatter/records (``records.ALLOWED_TARGETS``) : ``crm.lead``, ``crm.client`` ;
* champs personnalisés (``customfields.Module``) : ``lead``, ``client`` ;
* import/export (``dataimport`` ExportSpec/FIELD_MAPS) : ``leads``, ``clients`` ;
* actions agentiques (``apps.crm.agent_actions``, registre AG1) ;
* automatisations temporelles (``automation.DATE_TRIGGER_TARGETS``) : ``crm.lead``
  / ``relance_date`` ;
* KPI/agrégats de reporting (``reporting/reports.sales_report`` — funnel leads).

Les chaînes sont en français côté libellés ; les identifiants restent alignés sur
le code des surfaces (``'app.model'`` minuscule, comme ``records`` et le search).
"""
from __future__ import annotations

PLATFORM = {
    # Clé ModuleToggle (identique à ``CrmConfig.module_manifest['key']`` et à
    # l'app_label). Un CRM désactivé pour une société le retire de toutes les
    # surfaces d'un coup (gatage ODX23 dans ``core.platform``).
    'module': 'crm',

    # Modèles cherchables dans la recherche globale (reporting/search.py).
    'searchable_models': ['crm.lead', 'crm.client'],

    # Cibles chatter / pièces jointes / tags / liens GED (records.ALLOWED_TARGETS).
    'record_targets': ['crm.lead', 'crm.client'],

    # Modèles pouvant porter des champs personnalisés (customfields.Module).
    'customfield_models': ['lead', 'client'],

    # Entités import/export (clés ExportSpec / FIELD_MAPS de dataimport).
    'import_specs': ['leads', 'clients'],

    # Module dotted des actions agentiques CRM (registre AG1).
    'agent_actions_module': 'apps.crm.agent_actions',

    # Champs date/état surveillables par une automatisation temporelle
    # (automation.DATE_TRIGGER_TARGETS).
    'automation_state_fields': [
        {'model': 'crm.lead', 'field': 'relance_date'},
    ],

    # Fournisseurs de KPI/agrégats exposés au reporting (funnel commercial).
    'kpi_providers': ['crm_sales_report'],
}
