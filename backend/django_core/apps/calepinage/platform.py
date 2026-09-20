"""ARC28 — Manifeste plateforme du module « calepinage » (« déclarer une fois »).

Déclare ce que cette app expose aux 7 surfaces transverses (recherche globale,
chatter/records, champs personnalisés, import/export, actions agentiques,
automatisations temporelles, KPI). ``core.platform.collect_platform_manifests``
le collecte GÉNÉRIQUEMENT (aucun import de ``core`` vers l'app).

RÈGLE D'HONNÊTETÉ : ne déclarer une surface QUE si elle est réellement câblée.
Un identifiant listé ici sans le câblage réel est un « mensonge » que la
matrice de couverture (``core.platform_coverage``) détecte à l'envers. Trois
surfaces ont été câblées dans le lot (CAL27 recherche, CAL26 chatter, ARC31
champs perso) et sont donc déclarées ; les quatre autres restent VIDES tant
que leur câblage n'existe pas — voir le commentaire qui les accompagne.
"""
from __future__ import annotations

PLATFORM = {
    # Clé ``ModuleToggle`` — alignée sur
    # ``CalepinageConfig.module_manifest['key']``.
    'module': 'calepinage',

    # CAL27 — RECHERCHE GLOBALE : câblée dans le MÊME commit
    # (``apps/reporting/search.py::_spec_calepinage``, titre + client). Les
    # deux conditions de ``global_search`` sont donc remplies : la clé est
    # déclarée ICI et elle a une spec là-bas — l'une sans l'autre ne produit
    # rien.
    'searchable_models': ['calepinage.calepinage'],

    # CAL26 — CHATTER générique ``records`` : câblé (le viewset porte
    # ``ChatterViewSetMixin`` et ``services/journal.py`` écrit par
    # ``records.log_activity``). AUCUNE classe ``…Activity`` maison.
    'record_targets': ['calepinage.calepinage'],

    # ARC31 — CIBLE À CHAMPS PERSO : la déclaration EST le câblage (le
    # chargeur central ``apps/customfields/apps.py`` lit ce manifeste ; aucun
    # ``registry.register`` n'est écrit à la main).
    'customfield_models': ['calepinage'],

    # SURFACES DÉLIBÉRÉMENT VIDES — les déclarer serait un MENSONGE que la
    # matrice de couverture (``core.platform_coverage``) détecte à l'envers :
    #  * import/export : aucune spec ``dataimport`` n'existe pour ce module
    #    (un calepinage s'importerait mal : c'est une géométrie, pas une ligne
    #    de tableur) ;
    #  * actions agentiques : aucun module ``agent_actions`` n'est écrit ;
    #  * automatisation : le statut du calepinage ne déclenche aucune règle
    #    no-code aujourd'hui ;
    #  * KPI : aucun agrégat n'est publié dans ``reporting/reports.py``.
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
