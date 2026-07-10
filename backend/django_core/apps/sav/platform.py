"""ARC28/ARC29/ARC30 — Manifeste plateforme du module SAV (« déclarer une fois »).

Déclare ce que SAV expose aux surfaces transverses (voir ``core.platform``) :

* **recherche globale (ARC29)** — les 3 modèles SAV historiquement cherchables
  (Équipement, Ticket, ContratMaintenance) doivent être déclarés ici pour
  rester trouvables (``global_search`` est piloté par
  ``platform.searchable_models(company)``) ;
* **chatter/records (ARC30)** — la cible ``records.ALLOWED_TARGETS``
  historique (``sav.ticket``). Équipement et ContratMaintenance n'ont PAS de
  chatter générique (dérive héritée « recherche_sans_chatter », rendue visible
  et baselinée dans ``core.platform_coverage.BASELINE_DRIFT`` — à retirer le
  jour où ils recevront le chatter).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'sav',
    # ARC29 — modèles cherchables historiques (reporting/search.py).
    'searchable_models': [
        'sav.equipement', 'sav.ticket', 'sav.contratmaintenance',
    ],
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['sav.ticket'],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
