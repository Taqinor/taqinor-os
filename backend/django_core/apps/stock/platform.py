"""ARC28/ARC29 — Manifeste plateforme du module Stock (« déclarer une fois »).

Déclare ce que l'app Stock expose aux surfaces transverses (voir
``core.platform``). Avant ARC29, ``stock.Produit`` était importable,
customfieldable (``customfields.registry`` — clé ``produit``) et records-isé
(``records.ALLOWED_TARGETS`` contient ``('stock', 'produit')``, DC27) mais
restait INTROUVABLE dans la recherche globale (``reporting/search.py`` ne le
balayait pas) — un trou classique que la matrice de dérive ARC41 rend
désormais visible tant qu'il n'est pas déclaré ici.

Ce manifeste reflète le câblage RÉEL de Stock aujourd'hui :

* recherche globale (``reporting/search.py``, comblé par ARC29) : Produit ;
* cibles chatter/records (``records.ALLOWED_TARGETS``) : ``stock.produit``,
  ``stock.fournisseur`` (DC33) ;
* champs personnalisés (``customfields.registry``) : ``produit``,
  ``fournisseur`` (natifs historiques) ;
* import/export (``dataimport`` FIELD_MAPS, déclaré par ARC32) : ``products``,
  ``fournisseurs`` (cibles FG14 historiques — leurs mappings d'en-têtes
  restent dans ``dataimport.services.FIELD_MAPS``, seule la LISTE des cibles
  importables bascule sur ce manifeste) ;
* PAS d'actions agentiques déclarées via ce
  manifeste (``apps.stock.agent_actions`` existe et s'enregistre déjà depuis
  ``StockConfig.ready()`` — AG7 — donc HORS PÉRIMÈTRE d'auto-découverte
  ARC33 pour éviter un double enregistrement ; laissé vide ici) ;
* PAS d'automatisation temporelle, PAS de KPI dédié aujourd'hui.
"""
from __future__ import annotations

PLATFORM = {
    # Clé ModuleToggle (identique à ``StockConfig.module_manifest['key']``).
    'module': 'stock',

    # ARC29 — trou comblé : Produit devient cherchable dans la recherche
    # globale (voir apps/reporting/search.py::_spec_produit).
    'searchable_models': ['stock.produit'],

    # Cibles chatter / pièces jointes / tags / liens GED déjà câblées
    # (records.ALLOWED_TARGETS, DC27 + DC33).
    'record_targets': ['stock.produit', 'stock.fournisseur'],

    # Modèles pouvant porter des champs personnalisés (customfields.registry,
    # clés natives historiques 'produit' et 'fournisseur').
    'customfield_models': ['produit', 'fournisseur'],

    # ARC32 — cibles d'import déléguées à dataimport (clés FIELD_MAPS FG14).
    # Le MAPPING d'en-têtes reste dans dataimport.services.FIELD_MAPS ; ce
    # manifeste ne déclare que la LISTE des cibles importables (que
    # ``services.TARGETS`` unionne au registre, non-régression testée).
    'import_specs': ['products', 'fournisseurs'],
    # Vide À DESSEIN : apps.stock.agent_actions s'enregistre déjà depuis
    # StockConfig.ready() (AG7, register_stock_actions()) — le déclarer ici
    # ferait doublonner l'enregistrement une fois l'auto-découverte ARC33
    # branchée sur ce manifeste.
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
