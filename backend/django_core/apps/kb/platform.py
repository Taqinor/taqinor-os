"""ARC28/ARC30 — Manifeste plateforme du module KB (« déclarer une fois »).

Déclare ce que la base de connaissances expose aux surfaces transverses (voir
``core.platform``). ARC30 fait basculer la source de
``records.ALLOWED_TARGETS`` d'un ``set`` littéral figé vers l'union paresseuse
des manifestes ``record_targets`` — ce manifeste porte la cible chatter/records
historique (``kb.kbarticle`` — XKB10 pièces jointes/images, XKB13 commentaires
génériques réutilisant la même entrée).
"""
from __future__ import annotations

PLATFORM = {
    'module': 'kb',
    # ARC30 — cible chatter/records historique (records.ALLOWED_TARGETS).
    'record_targets': ['kb.kbarticle'],
    'searchable_models': [],
    # WIR67 — KbArticle est déclaré cible customfieldable ICI (clé
    # ``kb_article`` déjà consommée par ``ArticleEditor.jsx`` et validée par
    # ``kb.serializers.validate_proprietes`` via ``validate_custom_data``).
    # L'enregistrement passe par le CHARGEUR CENTRAL
    # ``customfields.registry.register_from_platform_manifests`` (ARC31) :
    # ``is_registered('kb_article')`` devient vrai → une ``CustomFieldDef``
    # module=``kb_article`` passe ``CustomFieldDefSerializer.validate_module``.
    # Note : les propriétés KB vivent dans le JSONField ``KbArticle.proprietes``
    # (pas via ``CustomRecord``), donc la résolution ``get_model`` de la clé
    # n'est jamais empruntée pour ce module.
    'customfield_models': ['kb_article'],
    'import_specs': [],
    'agent_actions_module': '',
    'automation_state_fields': [],
    'kpi_providers': [],
}
