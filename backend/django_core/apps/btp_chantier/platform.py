"""Manifeste plateforme du module BTP Chantier (ARC28/ARC30 — « déclarer une fois »).

Déclare les cibles chatter/pièces jointes (``records.ALLOWED_TARGETS``) pour
``ReserveChantier`` (NTCON1/2 — photos avant/après de levée) et
``JournalChantier`` (NTCON6 — photos du journal quotidien).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'btp_chantier',
    'record_targets': [
        'btp_chantier.reservechantier',
        'btp_chantier.journalchantier',
        'btp_chantier.rfireponse',
        # NTCON32 — cibles du CHATTER GÉNÉRIQUE (``records.Activity``, ARC8) :
        # journal automatique ancien→nouveau statut + notes manuelles. Jamais
        # un 2ᵉ mécanisme de commentaires propre à l'app.
        'btp_chantier.rfi',
        'btp_chantier.visadocument',
        'btp_chantier.avenantchantier',
        'btp_chantier.decomptegeneral',
    ],
    'searchable_models': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
