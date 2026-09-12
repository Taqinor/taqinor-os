"""NTAPI4 — `GET /api/public/v1/errors/` : catalogue d'erreurs consultable.

Document de DÉCOUVERTE global, exactement comme `openapi.json` (NTAPI20) et
le changelog API (NTAPI24) : il ne contient AUCUNE donnée de société, donc
aucune clé d'API n'est requise pour le lire — et il ne peut donc rien faire
fuiter d'un tenant vers un autre. C'est aussi la cible du `doc_url` posé par
l'enveloppe d'erreur NTAPI3 (`/api/public/v1/errors/#<code>`) : un intégrateur
qui reçoit une erreur peut lire son explication FR sans compte.

Le contenu vient d'`error_catalog.catalogue()`, dont les codes sont DÉRIVÉS de
la table du handler NTAPI3 (jamais réécrits à la main).
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ApiKeyRateThrottle
from .error_catalog import catalogue


@extend_schema(
    summary="Catalogue d'erreurs de l'API publique (NTAPI4).",
    responses=inline_serializer('PublicErrorCatalog', {
        'results': inline_serializer('PublicErrorCatalogEntry', {
            'code': serializers.CharField(),
            'titre': serializers.CharField(),
            'description': serializers.CharField(),
            'action': serializers.CharField(),
            'http_status': serializers.IntegerField(),
            'doc_url': serializers.CharField(),
        }, many=True),
    }),
)
class PublicErrorCatalogView(APIView):
    """``GET /api/public/v1/errors/`` — liste FR des codes d'erreur émis.

    Filtrable par ``?code=<code>`` pour ne renvoyer qu'une entrée (404 si le
    code n'existe pas — un code inconnu n'est jamais inventé)."""
    authentication_classes = []
    permission_classes = [AllowAny]
    # YRBAC9 — tout endpoint AllowAny déclare un throttle. Même classe que les
    # autres vues publiques (no-op sans clé, cf. ApiKeyRateThrottle) plutôt
    # que d'élargir l'allowlist THROTTLE_EXEMPT.
    throttle_classes = [ApiKeyRateThrottle]

    def get(self, request):
        entrees = catalogue()
        code = (request.query_params.get('code') or '').strip()
        if code:
            entrees = [e for e in entrees if e['code'] == code]
            if not entrees:
                return Response(
                    {'error': {
                        'type': 'invalid_request_error',
                        'code': 'not_found',
                        'message': f"Code d'erreur inconnu : « {code} ».",
                        'param': 'code',
                        'doc_url': '/api/public/v1/errors/#not_found',
                        'request_id': getattr(request, 'request_id', None),
                    }},
                    status=404)
        return Response({'results': entrees})
