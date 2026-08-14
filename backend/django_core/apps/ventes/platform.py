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

Les autres surfaces (customfields, import, agent, automation) restent HORS
PÉRIMÈTRE de ce manifeste : les clés customfields natives de Ventes
(``devis``) sont pré-enregistrées par ``customfields.registry`` lui-même et
``apps/ventes/agent_actions.py`` s'enregistre depuis ``VentesConfig.ready()``
— les déclarer ici les dupliquerait sans bénéfice.

* **KPI fédérés (PV82)** — ``kpi_providers`` porte désormais
  ``apps.ventes.reports.kpi_ventes`` (règle d'honnêteté ARC41 : un dotted
  déclaré doit être réellement résoluble). Trois tuiles « conçu vs vendu » —
  kWc conçus, kWc signés, taux de conversion des devis conçus — dérivées du
  seul ``Devis.roof_layout``/``Devis.etude_params``/``Devis.statut``. Aucun
  prix, aucune marge, aucun ``prix_achat`` n'y transite.
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
    # PV45 — le dossier réglementaire devient une cible de pièce jointe : le
    # schéma unifilaire généré s'y attache par ``records.Attachment`` (jamais
    # un FileField, ARC26).
    'record_targets': [
        'ventes.devis', 'ventes.boncommande', 'facturation.facture',
        'ventes.regulatorydossier',
    ],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    # PV82/ARC40 — provider KPI du domaine Ventes : un CALLABLE dotted résolu
    # à l'exécution par ``apps/reporting/reports.py::kpi_federes``, appelé
    # ``provider(company)``. Réellement câblé (règle d'honnêteté ARC41) :
    # ``apps.ventes.reports.kpi_ventes`` existe et rend des tuiles normalisées
    # ``{id, label, valeur, unite?}``. Aucun coût, aucune marge n'y transite.
    'kpi_providers': ['apps.ventes.reports.kpi_ventes'],
}
