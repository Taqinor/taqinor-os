"""NTAPI24 — fil « changelog API » dédié, sous /api/public/.

Réutilise/étend FG399 (`core.models.ChangelogEntry`) au lieu d'un modèle
dupliqué : ce fil est le SOUS-ENSEMBLE des notes de version marquées
`categorie` API-pertinente, réellement destiné aux intégrateurs externes
(breaking/feature/fix, version affectée, date). Document de découverte
GLOBAL (comme `openapi.json`, NTAPI20) — aucune donnée de société, donc
aucune authentification par clé requise.
"""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ChangelogEntry

from .auth import ApiKeyRateThrottle

# Correspondance NTAPI24 (breaking/feature/fix) ↔ FG399 (`categorie`
# nouveauté/amélioration/correctif) — jamais un second jeu de catégories.
_TYPE_BY_CATEGORIE = {
    ChangelogEntry.CAT_NOUVEAUTE: 'feature',
    ChangelogEntry.CAT_AMELIORATION: 'feature',
    ChangelogEntry.CAT_CORRECTIF: 'fix',
}


def _serialize(entry):
    type_ = 'breaking' if entry.breaking else _TYPE_BY_CATEGORIE.get(
        entry.categorie, 'feature')
    return {
        'id': entry.id,
        'titre': entry.titre,
        'corps': entry.corps,
        'version': entry.version,
        'type': type_,
        'breaking': entry.breaking,
        'date': entry.publie_le.isoformat() if entry.publie_le else None,
    }


class PublicChangelogView(APIView):
    """``GET /api/public/changelog/`` — fil des notes de version PUBLIÉES,
    triable/filtrable par ``?version=``. Aucune clé d'API requise (document
    de découverte global, sans donnée de société)."""
    authentication_classes = []
    permission_classes = [AllowAny]
    # YRBAC9 — tout endpoint AllowAny déclare un throttle. Fil public keyless
    # (comme openapi.json) : rien à brute-forcer, mais on garde la même classe
    # de throttle que les autres vues publiques de l'app (no-op sans clé, cf.
    # ApiKeyRateThrottle) plutôt que d'élargir l'allowlist THROTTLE_EXEMPT.
    throttle_classes = [ApiKeyRateThrottle]

    def get(self, request):
        qs = ChangelogEntry.objects.filter(publie=True).order_by(
            '-publie_le', '-id')
        version = request.query_params.get('version')
        if version:
            qs = qs.filter(version=version)
        return Response({'results': [_serialize(e) for e in qs]})
