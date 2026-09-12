"""ARC28 — Manifeste plateforme du module « Visites terrain » (VTA1).

Déclare ce que cette app expose aux 7 surfaces transverses.
``core.platform.collect_platform_manifests`` le collecte GÉNÉRIQUEMENT (aucun
import de ``core`` vers l'app) ; un module désactivé pour une société
disparaît alors de TOUTES les surfaces d'un coup.

RÈGLE D'HONNÊTETÉ (ARC41) : ``core/platform_coverage.py`` fait rougir la CI sur
toute surface DÉCLARÉE et non câblée. Le move VTA ne CRÉE aucune surface
transverse : il déplace du code existant. Les 7 surfaces restent donc vides,
chacune avec sa raison :

* ``searchable_models`` / ``record_targets`` restent VIDES. Le chatter d'une
  visite n'a jamais existé : la visite écrit ses quatre moments dans le chatter
  du LEAD (``crm.LeadActivity``), qui est le journal commun de tout ce qui
  arrive à un lead — ouvrir ici un second historique serait exactement la dette
  des 13 chatters hand-rollés. Et les deux surfaces avancent ENSEMBLE ou pas du
  tout (déclarer l'une sans l'autre crée une dérive NOUVELLE, donc rouge).
* ``customfield_models`` reste VIDE : aucun modèle de cette app ne porte de
  champ ``custom_data``. Le déclarer donnerait un écran de champs
  personnalisés qui accepte la saisie et la jette en silence.
* ``import_specs`` reste VIDE : une visite se saisit sur le terrain, elle ne
  s'importe pas d'un fichier.
* ``agent_actions_module`` reste VIDE : aucun module ``agent_actions`` ici.
* ``automation_state_fields`` reste VIDE. ``VisiteTerrain.statut`` ne change
  que par les transitions dédiées (``terminer``/``valider``/``renvoyer``) —
  l'ouvrir aux automatisations temporelles contournerait ce point de passage
  et ferait donner un feu vert par une horloge, alors que le feu vert est
  précisément la décision d'un humain.
* ``kpi_providers`` reste VIDE : aucun fournisseur de KPI dans cette app.
"""
from __future__ import annotations

PLATFORM = {
    # Clé ``ModuleToggle`` — alignée sur ``VisitesConfig.module_manifest``.
    'module': 'visites',

    'searchable_models': [],
    'record_targets': [],
    'customfield_models': [],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
