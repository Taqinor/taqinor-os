"""ARC28 — Manifeste plateforme du module Douane (« déclarer une fois »).

NTLOG49 — ``record_targets`` déclare ``DossierExport`` comme cible
chatter/follower/tag génériques (ARC8/XKB34/FG9) : suivre un dossier via
``records.Follower`` fait apparaître ses changements de statut (posés par
``apps/douane/services.py::tracer_transition_statut_dossier_export``, qui
écrit dans ``records.Activity`` via l'entonnoir unique ``apps.audit.
recorder.record_field_change``) dans le flux d'activité générique — sans
dupliquer de journal maison (ce module n'en a pas). Sans cette déclaration,
``records.ALLOWED_TARGETS``/``records.Follower``/``records.Comment``/
``records.TaggedItem`` refusent cette cible (« Type de cible non
autorisé »).

Volet IMPORT (``DossierImport``) NON déclaré ici : NTLOG10 reste BLOCKED
(GARDE WIR80, voir ``apps/douane/apps.py``) — seul le volet EXPORT existe
réellement dans cette app aujourd'hui.

Surface ``searchable_models`` VOLONTAIREMENT vide : ``DossierExport`` est
chatter-isé mais pas encore cherchable — dérive connue et ASSUMÉE, réservée
dans ``core.platform_coverage.BASELINE_DRIFT`` (même motif que
``transport.ordretransport`` avant que sa propre lane câble
``apps/reporting/search.py``, une app HORS du périmètre d'écriture de la
lane SUPPLY)."""
from __future__ import annotations

PLATFORM = {
    'module': 'douane',
    'record_targets': ['douane.dossierexport'],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
