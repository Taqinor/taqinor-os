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
  jour où ils recevront le chatter) ;
* **import (ARC32)** — cible ``equipements`` (parc SAV, FG14) : le mapping
  d'en-têtes reste dans ``dataimport.services.FIELD_MAPS`` ; seule la LISTE des
  cibles importables bascule sur ce manifeste ;
* **automation (ARC34)** — le couple (``sav.ticket``, ``statut``) est déclaré
  automatisable (``automation_state_fields``) : une règle no-code
  ``RECORD_STATE_CHANGE`` réagit aux transitions de statut du ticket.
  L'émission part du SERVICE (``apps.sav.services.
  emettre_changement_statut_ticket``, appelé par l'unique site de transition
  gardée ``TicketViewSet._appliquer_transition_statut``, à côté de l'émission
  ARC37) ; statut de DOMAINE ``Ticket.Statut``, jamais STAGES.py (rule #2).
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
    # ARC32 — cible d'import Équipements (parc SAV, clé FIELD_MAPS FG14).
    'import_specs': ['equipements'],
    'agent_actions_module': '',
    # ARC34 — statut Ticket automatisable par une règle no-code
    # RECORD_STATE_CHANGE (whitelist registre ; émission via services).
    'automation_state_fields': [
        {'model': 'sav.ticket', 'field': 'statut'},
    ],
    'kpi_providers': [],
}
