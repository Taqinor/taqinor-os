"""ARC28/ARC29/ARC30 — Manifeste plateforme du module Ventes
(« déclarer une fois »).

Déclare ce que Ventes expose aux surfaces transverses (voir ``core.platform``) :

* **recherche globale (ARC29)** — ``global_search`` est désormais piloté par
  ``platform.searchable_models(company)`` : les 3 modèles Ventes historiquement
  cherchables (Devis, Facture, BonCommande) doivent être déclarés ici pour
  rester trouvables (non-régression garantie par tests) ;
* **chatter/records (ARC30)** — les 3 cibles ``records.ALLOWED_TARGETS``
  historiques (Devis, BonCommande, Facture ; GED6 a ajouté BonCommande pour
  rattacher un document GED à toute la chaîne devis→commande→facture).

Les autres surfaces (customfields, import, agent, automation, KPI) restent
HORS PÉRIMÈTRE de ce manifeste : les clés customfields natives de Ventes
(``devis``) sont pré-enregistrées par ``customfields.registry`` lui-même et
``apps/ventes/agent_actions.py`` s'enregistre depuis ``VentesConfig.ready()``
— les déclarer ici les dupliquerait sans bénéfice.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'ventes',
    # ARC29 — modèles cherchables historiques (reporting/search.py).
    'searchable_models': [
        'ventes.devis', 'ventes.facture', 'ventes.boncommande',
    ],
    # ARC30 — cibles chatter/records historiques (records.ALLOWED_TARGETS).
    # ODX17 a déplacé Facture vers l'app ``facturation`` (state-only) : la cible
    # chatter/records est résolue en ContentType, donc l'app_label DOIT suivre le
    # modèle (``facturation.facture``), sinon la résolution est cassée.
    'record_targets': [
        'ventes.devis', 'ventes.boncommande', 'facturation.facture',
    ],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
