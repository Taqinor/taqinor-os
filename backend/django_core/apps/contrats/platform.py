"""ARC28 — Manifeste plateforme du module Contrats (« déclarer une fois »).

Déclare ce que l'app Contrats expose aux surfaces transverses (voir
``core.platform``). Il reflète le câblage RÉEL d'aujourd'hui, qui est ASYMÉTRIQUE
par rapport au CRM — et c'est VOULU : le contrat reçoit le chatter générique
(``records.ALLOWED_TARGETS`` contient ``('contrats', 'contrat')``, ARC8) mais
n'est PAS encore branché sur les autres surfaces :

* PAS de recherche globale (absent de ``reporting/search.py``) ;
* PAS de champs personnalisés (absent de ``customfields.Module``) ;
* PAS d'import/export (absent de ``dataimport``) ;
* PAS d'actions agentiques (aucun ``apps/contrats/agent_actions.py``) ;
* PAS d'automatisation temporelle (absent de ``automation.DATE_TRIGGER_TARGETS``) ;
* PAS de KPI/agrégat dédié (absent de ``reporting/reports.py``).

Déclarer ce manifeste À COMPTE HONNÊTE (une seule surface remplie) rend cette
dérive VISIBLE et mesurable : la matrice de couverture ARC41 croisera ce
manifeste pour signaler « contrat chatter-isé mais introuvable en recherche /
non customfieldable » au lieu de laisser le trou silencieux. Les surfaces
manquantes se rempliront quand elles seront branchées (tâches ultérieures).
"""
from __future__ import annotations

PLATFORM = {
    # Clé ModuleToggle (identique à ``ContratsConfig.module_manifest['key']``).
    'module': 'contrats',

    # SEULE surface câblée aujourd'hui : chatter/records générique (ARC8).
    'record_targets': ['contrats.contrat'],

    # Surfaces DÉLIBÉRÉMENT VIDES (le contrat n'y est pas encore branché) —
    # laissées explicites pour documenter la dérive que la matrice ARC41 doit
    # remonter. Ne pas « remplir pour faire joli » : un identifiant ici sans le
    # câblage réel de la surface serait un mensonge que la matrice détecterait à
    # l'envers (déclaré mais absent du code de la surface).
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
