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

NTIDE50 — ``kpi_providers`` déclare ``selectors.kpi_innovation`` : tuiles
« Idées cette semaine » + top idée votée, agrégées par l'endpoint reporting
fédéré (ARC40, ``GET /reporting/reports/kpi-federes/``) sans que le
reporting importe un seul modèle de cette app.
"""
from __future__ import annotations

PLATFORM = {
    'module': 'innovation',
    # Chatter/tags génériques (ARC8/FG9).
    'record_targets': ['innovation.idee'],
    'kpi_providers': ['apps.innovation.selectors.kpi_innovation'],
}
