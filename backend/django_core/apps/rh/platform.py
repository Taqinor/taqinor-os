"""ARC28/ARC30/ARC33/ARC40 — Manifeste plateforme du module RH
(« déclarer une fois »).

Déclare ce que RH expose aux surfaces transverses (voir ``core.platform``) :

* **chatter/records (ARC30)** — la cible ``records.ALLOWED_TARGETS``
  historique (``rh.dossieremploye``) ;
* **actions agent (ARC33, pilote)** — ``apps.rh.agent_actions`` (lecture/liste
  seule : employés, demandes de congé), AUTO-DÉCOUVERT par
  ``AgentConfig.ready()`` depuis cette déclaration — aucun câblage dans
  ``RhConfig.ready()``. Module ``ModuleToggle``-OFF ⇒ actions absentes du
  catalogue ;
* **KPI reporting (ARC40, pilote)** — ``apps.rh.selectors.
  kpi_effectifs_absences`` (effectif actif, absences en cours), agrégé par
  l'endpoint fédéré ``reports/kpi-federes/``. Module OFF ⇒ tuiles absentes.

Les autres surfaces restent vides ici (hors périmètre).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'rh',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['rh.dossieremploye'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    # ARC33 — actions agentiques lecture seule, auto-découvertes.
    'agent_actions_module': 'apps.rh.agent_actions',
    'automation_state_fields': [],
    # ARC40 — provider KPI (callable dotted, résolu par le reporting fédéré).
    'kpi_providers': ['apps.rh.selectors.kpi_effectifs_absences'],
}
