"""Manifeste plateforme du module Innovation (ARC28 — « déclarer une fois »).

Déclare ``innovation.idee`` comme cible chatter/tag générique
(``records.ALLOWED_TARGETS``, ARC8/FG9) : le « historique » d'une idée
(NTIDE5) et le marquage en masse (NTIDE13) réutilisent ``apps.records``
(``Activity``/``Tag``/``TaggedItem`` via ``ContentType``) au lieu de créer un
nouveau modèle ``*Activity`` maison (ce que ``scripts/check_platform.py``
(ARC8) interdit pour tout modèle NOUVEAU).

Surfaces volontairement VIDES pour ce lot (NTIDE1-13) : pas encore cherchable
(``searchable_models``), pas de champs personnalisés (``customfield_models``),
pas d'action agentique, pas d'import/export dataimport, pas de statut
automatisable — un lot futur (NTIDE14+) les branchera si besoin.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'innovation',
    # Chatter/tags génériques (ARC8/FG9).
    'record_targets': ['innovation.idee'],
}
