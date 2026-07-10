"""ARC28/ARC29 — Manifeste plateforme du module Contrats (« déclarer une fois »).

Déclare ce que l'app Contrats expose aux surfaces transverses (voir
``core.platform``). Il reflétait à l'origine (ARC28) un câblage ASYMÉTRIQUE :
le contrat recevait le chatter générique (``records.ALLOWED_TARGETS`` contient
``('contrats', 'contrat')``, ARC8) mais restait invisible en recherche globale
— un trou que la matrice de dérive ARC41 rendait visible via
``BASELINE_DRIFT`` (``'contrats.contrat', 'chatter_sans_recherche'``).

ARC29 comble ce trou précis : Contrat est désormais cherchable
(``reporting/search.py::_spec_contrat``) — l'entrée ``BASELINE_DRIFT``
correspondante est retirée dans le même commit (elle mentirait sinon : la
dérive n'existe plus).

Surfaces encore VOLONTAIREMENT vides (le contrat n'y est pas branché) :

* PAS de champs personnalisés déclarés via ce manifeste (la cible pilote ARC14
  reste enregistrée par ``ContratsConfig.ready()`` jusqu'à ARC31) ;
* PAS d'import/export (absent de ``dataimport``) ;
* PAS d'actions agentiques déclarées via ce manifeste ;
* PAS d'automatisation temporelle (absent de ``automation.DATE_TRIGGER_TARGETS``) ;
* PAS de KPI/agrégat dédié (absent de ``reporting/reports.py``).

Laissées explicites (jamais « remplies pour faire joli ») : un identifiant ici
sans le câblage réel de la surface serait un mensonge que la matrice ARC41
détecterait à l'envers (déclaré mais absent du code de la surface).
"""
from __future__ import annotations

PLATFORM = {
    # Clé ModuleToggle (identique à ``ContratsConfig.module_manifest['key']``).
    'module': 'contrats',

    # Chatter/records générique (ARC8).
    'record_targets': ['contrats.contrat'],

    # ARC29 — trou comblé : Contrat devient cherchable (voir
    # apps/reporting/search.py::_spec_contrat). Retire l'entrée BASELINE_DRIFT
    # 'chatter_sans_recherche' correspondante dans core/platform_coverage.py.
    'searchable_models': ['contrats.contrat'],

    # Surfaces DÉLIBÉRÉMENT VIDES (le contrat n'y est pas encore branché).
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
