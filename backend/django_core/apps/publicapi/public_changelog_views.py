"""NTAPI24 — fil « changelog API » dédié, sous /api/public/v1/.

Réutilise/étend FG399 (`core.models.ChangelogEntry`) au lieu d'un modèle
dupliqué : ce fil est le SOUS-ENSEMBLE des notes de version marquées
`categorie` API-pertinente, réellement destiné aux intégrateurs externes
(breaking/feature/fix, version affectée, date). Document de découverte
GLOBAL (comme `openapi.json`, NTAPI20) — aucune donnée de société, donc
aucune authentification par clé requise.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, inline_serializer,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ChangelogEntry

from .auth import ApiKeyRateThrottle

#: Borne du filtre ``?version=`` = ``ChangelogEntry.version.max_length`` (40).
VERSION_MAX = ChangelogEntry._meta.get_field('version').max_length
#: Même prédicat que le contrôle serveur : sans NUL, longueur bornée — déclaré
#: au schéma pour que le fuzz ne génère que des valeurs acceptées.
MOTIF_VERSION = r'^[^\u0000]{0,%d}$' % VERSION_MAX

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
    """``GET /api/public/v1/changelog/`` — fil des notes de version PUBLIÉES,
    triable/filtrable par ``?version=``. Aucune clé d'API requise (document
    de découverte global, sans donnée de société)."""
    authentication_classes = []
    permission_classes = [AllowAny]
    # YRBAC9 — tout endpoint AllowAny déclare un throttle. Fil public keyless
    # (comme openapi.json) : rien à brute-forcer, mais on garde la même classe
    # de throttle que les autres vues publiques de l'app (no-op sans clé, cf.
    # ApiKeyRateThrottle) plutôt que d'élargir l'allowlist THROTTLE_EXEMPT.
    throttle_classes = [ApiKeyRateThrottle]

    @extend_schema(
        parameters=[OpenApiParameter(
            'version', OpenApiTypes.STR, required=False,
            description="Filtre par version (sans caractère nul, "
                        f"{VERSION_MAX} caractères au plus).",
            pattern=MOTIF_VERSION)],
        responses=inline_serializer('PublicChangelog', {
            'results': inline_serializer('PublicChangelogEntree', {
                'id': serializers.IntegerField(),
                'titre': serializers.CharField(),
                'corps': serializers.CharField(),
                'version': serializers.CharField(allow_blank=True),
                'type': serializers.CharField(),
                'breaking': serializers.BooleanField(),
                'date': serializers.CharField(allow_null=True)},
                many=True)}))
    def get(self, request):
        qs = ChangelogEntry.objects.filter(publie=True).order_by(
            '-publie_le', '-id')
        version = request.query_params.get('version')
        if version:
            # Postgres refuse NUL dans un littéral : 400 net, jamais un 500.
            if '\x00' in version or len(version) > VERSION_MAX:
                raise ValidationError({
                    'version': 'Version invalide (caractère nul interdit, '
                               f'{VERSION_MAX} caractères au plus).'})
            qs = qs.filter(version=version)
        return Response({'results': [_serialize(e) for e in qs]})
