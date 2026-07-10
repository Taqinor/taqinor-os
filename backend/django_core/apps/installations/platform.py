"""ARC28/ARC29/ARC30 — Manifeste plateforme du module Installations
(« déclarer une fois »).

Déclare ce que Installations expose aux surfaces transverses (voir
``core.platform``) :

* **recherche globale (ARC29)** — le chantier (``installations.installation``)
  est historiquement cherchable et alimente DEUX groupes de résultats
  (« Chantiers » par référence, « Dossiers réglementaires » par
  dossier_reference/opérateur) — les deux specs vivent dans
  ``apps/reporting/search.py`` sous la même clé de modèle ;
* **chatter/records (ARC30)** — la cible ``records.ALLOWED_TARGETS``
  historique (``installations.installation``) ; SCA34 ajoute
  ``installations.ordresoustraitance`` et SCA36 ``installations.demandeachat``
  (pilotes du kit ``core.documents`` — chatter câblé sur leurs viewsets via
  ``ChatterViewSetMixin``).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'installations',
    # ARC29 — modèle cherchable historique (2 groupes : chantier + dossier).
    'searchable_models': ['installations.installation'],
    # ARC30 — cibles chatter/records (records.ALLOWED_TARGETS). SCA34 ajoute
    # ordresoustraitance, SCA36 demandeachat (pilotes kit core.documents,
    # chatter câblé sur leurs viewsets).
    'record_targets': [
        'installations.installation',
        'installations.ordresoustraitance',
        'installations.demandeachat',
    ],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
