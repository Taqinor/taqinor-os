"""ARC28/ARC29/ARC31/ARC33 — Manifeste plateforme du module Contrats
(« déclarer une fois »).

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

ARC31 — Contrat est déclaré cible customfieldable ICI (``customfield_models``)
au lieu d'un appel explicite ``customfields.registry.register(...)`` dans
``ContratsConfig.ready()`` — la SOURCE de peuplement du registre bascule vers
un chargeur central unique (``apps/customfields/apps.py``) qui lit ce
manifeste ; l'API ``registry.register``/``get_model`` reste inchangée.

ARC33 — ``apps.contrats.agent_actions`` (LECTURE seule : liste des contrats)
est déclaré dans ``agent_actions_module`` et AUTO-DÉCOUVERT par
``AgentConfig.ready()`` — aucun câblage dans ``ContratsConfig.ready()``.
Module ``ModuleToggle``-OFF ⇒ actions absentes du catalogue agent.

Surfaces encore VOLONTAIREMENT vides (le contrat n'y est pas branché) :

* PAS d'import/export (absent de ``dataimport``) ;
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

    # ARC31 — cible customfieldable (pilote historique ARC14 ; source
    # basculée depuis ContratsConfig.ready() vers ce manifeste).
    'customfield_models': ['contrat'],

    # ARC33 — actions agentiques LECTURE seule (liste des contrats),
    # auto-découvertes par AgentConfig.ready() depuis cette déclaration.
    'agent_actions_module': 'apps.contrats.agent_actions',

    # Surfaces DÉLIBÉRÉMENT VIDES (le contrat n'y est pas encore branché).
    'import_specs': [],
    'automation_state_fields': [],
    'kpi_providers': [],
}
