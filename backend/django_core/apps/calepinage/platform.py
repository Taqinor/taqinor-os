"""ARC28 — Manifeste plateforme du module « calepinage » (« déclarer une fois »).

Déclare ce que cette app expose aux 7 surfaces transverses (recherche globale,
chatter/records, champs personnalisés, import/export, actions agentiques,
automatisations temporelles, KPI). ``core.platform.collect_platform_manifests``
le collecte GÉNÉRIQUEMENT (aucun import de ``core`` vers l'app).

RÈGLE D'HONNÊTETÉ : ne déclarer une surface QUE si elle est réellement câblée.
Un identifiant listé ici sans le câblage réel est un « mensonge » que la
matrice de couverture (``core.platform_coverage``) détecte à l'envers. Les
surfaces sont donc VIDES au jour 1 (CAL4) et se remplissent par CAL27 quand
recherche / chatter / champs perso / import / agent / KPI seront branchés.
"""
from __future__ import annotations

PLATFORM = {
    # Clé ``ModuleToggle`` — alignée sur
    # ``CalepinageConfig.module_manifest['key']``.
    'module': 'calepinage',

    # Les 7 surfaces — vides tant qu'elles ne sont pas câblées (CAL27).
    'searchable_models': [],       # 'app.model' cherchables (reporting/search)
    'record_targets': [],          # 'app.model' chatter/records (ALLOWED_TARGETS)
    'customfield_models': [],      # 'model' à champs perso (customfields)
    'import_specs': [],            # entités import/export (dataimport)
    'agent_actions_module': '',    # 'apps.calepinage.agent_actions'
    'automation_state_fields': [],  # [{'model': 'app.model', 'field': 'statut'}]
    'kpi_providers': [],           # fournisseurs de KPI/agrégats (reporting)
}
