"""ARC28/ARC40 — Manifeste plateforme du module `uxviews` (« déclarer une
fois »).

Déclare ce que `uxviews` expose aux surfaces transverses (voir
`core.platform`) :

* **KPI reporting (NTUX40)** — `apps.uxviews.selectors.kpi_adoption_ux`
  (adoption des vues par défaut de rôle, vues personnelles par utilisateur
  actif, usage de l'édition en masse), agrégé par l'endpoint fédéré
  `reports/kpi-federes/`. Module OFF (n'arrivera jamais : `installable:
  False`, fondation toujours active) ⇒ tuiles absentes, comme tout provider.

Les autres surfaces restent vides ici (hors périmètre de ce lot).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'uxviews',
    'record_targets': [],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    # NTUX40 — provider KPI (callable dotted, résolu par le reporting fédéré).
    'kpi_providers': ['apps.uxviews.selectors.kpi_adoption_ux'],
}
