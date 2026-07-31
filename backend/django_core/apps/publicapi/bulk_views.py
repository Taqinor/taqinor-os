"""NTAPI14/15/16/43/30 — endpoints bulk (export/import/jobs/pull CSV) de
l'API publique.

Distinct de `public_views.py` (lecture synchrone paginée) et
`public_write_views.py` (écriture unitaire synchrone) : les endpoints
export/import/jobs/relancer CRÉENT un `BulkJob` (`bulk.py`) traité HORS
requête (Celery) et renvoient 202 immédiatement — jamais de time-out HTTP
même sur un très gros volume (NTAPI14 « exporter 50 000 leads produit un
fichier complet sans time-out HTTP »). `PublicCsvPullExportView` (NTAPI30)
est l'exception SYNCHRONE de ce module : un GET simple répondant en CSV
immédiat, pour `=IMPORTDATA()` Google Sheets/Excel Web.

Le scope requis dépend de l'ENTITÉ demandée, jamais d'un scope bulk séparé —
voir `constants.EXPORT_SCOPE_BY_ENTITY`/`IMPORT_SCOPE_BY_ENTITY`.
"""
import csv
import io

from django.http import HttpResponse

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import (
    NotAuthenticated, PermissionDenied, ValidationError,
)
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import ApiKeyAuthentication, ApiKeyRateThrottle, QueryTokenAuthentication
from .bulk import (
    BulkJobError, create_export_job, create_import_job, relancer_job,
    _export_registry, _serialize_row,
)
from .constants import EXPORT_SCOPE_BY_ENTITY, IMPORT_SCOPE_BY_ENTITY
from .models import ApiKey, BulkJob
from .public_response import PublicApiResponseMixin
from .public_serializers import BulkJobSerializer


class HasAnyApiKey(BasePermission):
    """Exige une clé API valide, SANS scope métier précis — pour les
    endpoints « méta » (suivi de job) dont l'accès est déjà borné à la
    société de la clé (`get_queryset`) : aucun scope supplémentaire n'a de
    sens (un job appartient à la société, pas à UN scope)."""

    def has_permission(self, request, view):
        return isinstance(getattr(request, 'auth', None), ApiKey)


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


class PublicImportCreateView(_BulkPostAPIView):
    """POST /api/public/imports/ (NTAPI15) — lance un import bulk asynchrone
    (leads/activités). Multipart : champ fichier ``file`` (CSV/JSONL, détecté
    par l'extension) + champs ``entite``/``mode``/``dedup_key``.

    Mode ``upsert`` : ``dedup_key`` (``email``/``telephone``) — un rejeu du
    même fichier NE duplique jamais (recherche l'existant avant de créer)."""

    def post(self, request):
        api_key = self._api_key(request)
        entite = (request.data.get('entite') or '').strip()
        self._check_scope(api_key, IMPORT_SCOPE_BY_ENTITY.get(entite))
        upload = request.FILES.get('file')
        file_bytes = upload.read() if upload is not None else None
        try:
            job = create_import_job(
                company=api_key.company, api_key=api_key, entite=entite,
                mode=request.data.get('mode', 'create'),
                dedup_key=request.data.get('dedup_key'),
                file_bytes=file_bytes,
                filename=getattr(upload, 'name', ''))
        except BulkJobError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(
            BulkJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class PublicJobViewSet(PublicApiResponseMixin, viewsets.ReadOnlyModelViewSet):
    """GET /api/public/jobs/ + /jobs/<id>/ (NTAPI16) — suivi d'un BulkJob.
    POST /api/public/jobs/<id>/relancer/ (NTAPI43) — reprise sur curseur.

    Un job n'est JAMAIS visible hors de la société de la clé
    (``get_queryset``) — cross-tenant impossible quelle que soit la clé
    utilisée, aucun scope métier supplémentaire requis (``HasAnyApiKey``)."""
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasAnyApiKey]
    throttle_classes = [ApiKeyRateThrottle]
    serializer_class = BulkJobSerializer
    queryset = BulkJob.objects.all()

    def get_queryset(self):
        return super().get_queryset().filter(
            company_id=self.request.auth.company_id)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # NTAPI16 — poll-friendly : `Retry-After` conseillé tant que `en_cours`
        # (uniquement pertinent sur le détail — un `retrieve` renvoie un dict
        # plat avec `statut`, jamais une page de liste).
        data = getattr(response, 'data', None)
        if isinstance(data, dict) and data.get('statut') == BulkJob.STATUT_EN_COURS:
            response['Retry-After'] = '3'
        return response

    @action(detail=True, methods=['post'], url_path='relancer')
    def relancer(self, request, pk=None):
        job = self.get_object()  # scope société déjà appliqué par get_queryset
        try:
            job = relancer_job(job)
        except BulkJobError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(BulkJobSerializer(job).data)


class PublicCsvPullExportView(PublicApiResponseMixin, APIView):
    """GET /api/public/exports/<entite>.csv?token=<clé> (NTAPI30) — export
    live SYNCHRONE en CSV, exploitable par ``=IMPORTDATA()`` de Google
    Sheets/Excel Web (rafraîchi côté tableur à chaque recalcul — le tableur
    ne fait qu'un GET brut, aucun en-tête custom possible, d'où le token en
    QUERY STRING plutôt que l'en-tête ``Authorization`` habituel).

    Distinct de ``PublicExportCreateView`` (NTAPI14, asynchrone/BulkJob,
    gros volumes) : ici la réponse est le CSV lui-même, immédiate, pour un
    usage tableur interactif. Scope READ-ONLY STRICT (même mapping que
    NTAPI14, ``EXPORT_SCOPE_BY_ENTITY``) — un token qui fuite (log, historique
    navigateur, feuille partagée) ne peut jamais rien écrire. Réutilise les
    MÊMES querysets/serializers publics que la lecture synchrone (jamais de
    prix d'achat ni de coût exposé).
    """
    authentication_classes = [QueryTokenAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ApiKeyRateThrottle]

    def get(self, request, entite):
        api_key = request.auth
        if not isinstance(api_key, ApiKey):
            # Aucun jeton fourni du tout (distinct d'un jeton INVALIDE, déjà
            # rejeté par `QueryTokenAuthentication.authenticate` en 401) —
            # `NotAuthenticated` (401), jamais `PermissionDenied` (403) :
            # « pas de justificatif » reste distinct de « droits insuffisants ».
            raise NotAuthenticated("Jeton requis (paramètre ?token=<clé>).")
        required_scope = EXPORT_SCOPE_BY_ENTITY.get(entite)
        if not required_scope:
            raise ValidationError({'entite': "Entité inconnue ou non exportable."})
        if not api_key.has_scope(required_scope):
            raise PermissionDenied(
                f"Ce jeton n'a pas le droit nécessaire ({required_scope}).")

        viewset_cls = _export_registry()[entite]
        serializer_class = viewset_cls.serializer_class
        queryset = viewset_cls.queryset.filter(company_id=api_key.company_id)

        buf = io.StringIO()
        writer = None
        for instance in queryset.iterator():
            row = _serialize_row(serializer_class, instance)
            if writer is None:
                writer = csv.DictWriter(buf, fieldnames=list(row.keys()))
                writer.writeheader()
            writer.writerow(row)
        if writer is None:
            # Aucune ligne : CSV STABLE quand même (en-têtes seuls, jamais un
            # corps vide qui casserait IMPORTDATA — « toujours une forme
            # tabulaire valide », même critère que le pull rempli).
            fieldnames = list(serializer_class().fields.keys())
            writer = csv.DictWriter(buf, fieldnames=fieldnames)
            writer.writeheader()

        resp = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'inline; filename="{entite}.csv"'
        return resp
