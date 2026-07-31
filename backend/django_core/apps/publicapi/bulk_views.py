"""NTAPI14 — endpoint bulk export de l'API publique.

Distinct de `public_views.py` (lecture synchrone paginée) et
`public_write_views.py` (écriture unitaire synchrone) : la requête ICI CRÉE
un `BulkJob` (`bulk.py`) traité HORS requête (Celery) et renvoie 202
immédiatement — jamais de time-out HTTP même sur un très gros volume (NTAPI14
« exporter 50 000 leads produit un fichier complet sans time-out HTTP »).

Le scope requis dépend de l'ENTITÉ demandée (`entite` dans le corps), jamais
d'un scope bulk séparé — voir `constants.EXPORT_SCOPE_BY_ENTITY`.

NTAPI15 (import), NTAPI16 (suivi de job) et NTAPI43 (reprise) s'AJOUTENT à ce
module dans une tâche suivante — sans rien réécrire ici.
"""
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ApiKeyAuthentication, ApiKeyRateThrottle
from .bulk import BulkJobError, create_export_job
from .constants import EXPORT_SCOPE_BY_ENTITY
from .models import ApiKey
from .public_response import PublicApiResponseMixin
from .public_serializers import BulkJobSerializer


class _BulkPostAPIView(PublicApiResponseMixin, APIView):
    """Base commune export/import : auth par clé, throttle par clé, AUCUN
    `required_scope` fixe (dépend de l'entité demandée — vérifié dans
    `post()`, comme `PublicWriteAPIView` le fait pour son propre scope
    fixe)."""
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ApiKeyRateThrottle]

    def _api_key(self, request):
        api_key = request.auth
        if not isinstance(api_key, ApiKey):
            raise PermissionDenied("Authentification par clé API requise.")
        return api_key

    def _check_scope(self, api_key, scope):
        if not scope:
            raise ValidationError({'entite': "Entité inconnue."})
        if not api_key.has_scope(scope):
            raise PermissionDenied(
                f"Cette clé API n'a pas le droit nécessaire ({scope}).")


class PublicExportCreateView(_BulkPostAPIView):
    """POST /api/public/exports/ (NTAPI14) — lance un export bulk asynchrone.

    Corps : ``{"entite": "leads", "format": "csv"|"jsonl", "filtres": {...}}``.
    Réutilise STRICTEMENT les serializers publics (jamais de prix d'achat) —
    voir `bulk._export_registry()`.
    """

    def post(self, request):
        api_key = self._api_key(request)
        entite = (request.data.get('entite') or '').strip()
        self._check_scope(api_key, EXPORT_SCOPE_BY_ENTITY.get(entite))
        try:
            job = create_export_job(
                company=api_key.company, api_key=api_key, entite=entite,
                fmt=request.data.get('format', 'csv'),
                filtres=request.data.get('filtres'))
        except BulkJobError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(
            BulkJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)
