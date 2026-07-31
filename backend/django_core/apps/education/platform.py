"""ARC28/ARC32 — Manifeste plateforme du module Éducation (« déclarer une
fois »).

NTEDU36 — cible d'import ``eleves_education`` (migration CSV/XLSX depuis
Excel/ancien système, réutilise EXCLUSIVEMENT ``apps/dataimport`` — jamais un
moteur d'import maison) déclarée ici : le mapping d'en-têtes vit dans
``dataimport.services.FIELD_MAPS`` et l'écriture reste DÉLÉGUÉE à
``apps.education.services.creer_eleve_import`` (jamais les modèles
``Eleve``/``Famille`` directement depuis ``dataimport`` — même motif XFLT22
que ``dossiers_rh``/``contrats``/``vehicules``). Seule la LISTE des cibles
importables bascule sur ce manifeste (``dataimport.services.TARGETS``
unionne ``FIELD_MAPS`` avec les ``import_specs`` déclarés).

Les autres surfaces (recherche, chatter, champs perso, actions agent,
automatisations, KPI) restent VOLONTAIREMENT vides ici — l'app Éducation
n'y est pas encore branchée dans ce lot.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'education',
    'searchable_models': [],
    'record_targets': [],
    'customfield_models': [],
    # NTEDU36 — cible d'import « Élèves » (Eleve/Famille), écriture déléguée.
    'import_specs': ['eleves_education'],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
