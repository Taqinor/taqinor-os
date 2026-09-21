"""ARC28/ARC30/ARC40 — Manifeste plateforme du module Gestion de projet
(« déclarer une fois »).

Déclare ce que Gestion de projet expose aux surfaces transverses (voir
``core.platform``) :

* **chatter/records (ARC30)** — la cible ``records.ALLOWED_TARGETS``
  historique (``gestion_projet.projet``, ARC26 — pièces jointes génériques) ;
* **KPI reporting (ARC40, pilote)** — ``apps.gestion_projet.selectors.
  kpi_projets_par_statut`` (répartition des projets par statut), agrégé par
  l'endpoint fédéré ``reports/kpi-federes/``. Module OFF ⇒ tuiles absentes.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'gestion_projet',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['gestion_projet.projet'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    # ARC40 — provider KPI (callable dotted, résolu par le reporting fédéré).
    'kpi_providers': ['apps.gestion_projet.selectors.kpi_projets_par_statut'],
}
