"""ARC28/ARC33/ARC40 — Manifeste plateforme du module Compta
(« déclarer une fois »).

Déclare ce que Compta expose aux surfaces transverses (voir ``core.platform``) :

* **actions agent (ARC33, pilote)** — ``apps.compta.agent_actions`` (LECTURE
  seule : liste des effets/échéances de trésorerie ; jamais de saisie/
  validation/clôture comptable par l'agent), AUTO-DÉCOUVERT par
  ``AgentConfig.ready()`` depuis cette déclaration — aucun câblage dans
  ``ComptaConfig.ready()``. Module ``ModuleToggle``-OFF ⇒ actions absentes du
  catalogue ;
* **KPI reporting (ARC40, pilote)** — ``apps.compta.selectors.kpi_echeances``
  (échéances d'effets à 30 j / dépassées), agrégé par l'endpoint fédéré
  ``reports/kpi-federes/``. Module OFF ⇒ tuiles absentes.

Les autres surfaces restent vides (la compta n'est branchée ni sur la
recherche globale, ni sur le chatter générique, ni sur les champs perso —
dérives à combler par des tâches ultérieures, chacune retirant sa ligne du
constat ci-dessus le jour du câblage).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'compta',
    'record_targets': [],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    # ARC33 — actions agentiques lecture seule, auto-découvertes.
    'agent_actions_module': 'apps.compta.agent_actions',
    'automation_state_fields': [],
    # ARC40 — provider KPI (callable dotted, résolu par le reporting fédéré).
    'kpi_providers': ['apps.compta.selectors.kpi_echeances'],
}
