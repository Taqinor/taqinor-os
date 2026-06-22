"""API REST de la GED — tout scopé société côté serveur.

Lecture : tout rôle authentifié. Écriture : responsable/admin. La société est
TOUJOURS posée côté serveur (TenantMixin) — jamais lue du corps de requête.
Les dossiers (Folder) ont un chemin matérialisé recalculé côté serveur, et les
versions de document sont numérotées + déduppées via `services`.
"""
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from . import services
from .models import Cabinet, Document, DocumentVersion, Folder
from .serializers import (
    CabinetSerializer, DocumentSerializer, DocumentVersionSerializer,
    FolderSerializer,
)

READ_ACTIONS = ['list', 'retrieve']


class CabinetViewSet(TenantMixin, viewsets.ModelViewSet):
    """Cabinets (armoires racines) d'une société."""
    queryset = Cabinet.objects.all()
    serializer_class = CabinetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class FolderViewSet(TenantMixin, viewsets.ModelViewSet):
    """Dossiers arborescents (chemin matérialisé). Filtrable par cabinet et
    parent ; expose le sous-arbre via l'action `descendants`."""
    queryset = Folder.objects.select_related('cabinet', 'parent').all()
    serializer_class = FolderSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'descendants':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def _resolve_company_folder(self, folder_id):
        """Résout un dossier de la société courante, ou None.

        Borne au queryset company-scopé (TenantMixin) : un id appartenant à
        une autre société renvoie None (jamais de fuite cross-société)."""
        if folder_id in (None, '', 'null'):
            return None
        return (Folder.objects.filter(company=self.request.user.company)
                .filter(pk=folder_id).first())

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        cabinet = params.get('cabinet')
        if cabinet:
            qs = qs.filter(cabinet_id=cabinet)
        parent = params.get('parent')
        if parent == 'null':
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)
        return qs

    def perform_create(self, serializer):
        # company posée côté serveur (jamais du corps).
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'], url_path='descendants')
    def descendants(self, request, pk=None):
        """Sous-arbre strict du dossier (via le chemin matérialisé)."""
        folder = self.get_object()
        qs = folder.descendants()
        data = FolderSerializer(qs, many=True, context={'request': request}).data
        return Response(data)

    @action(detail=True, methods=['post'], url_path='deplacer')
    def deplacer(self, request, pk=None):
        """Déplace ce dossier sous un nouveau parent (déplacement scopé société).

        Body : `{"parent": <id|null>}`. Le dossier source est company-scopé via
        `get_object()` (404 cross-société). Le parent cible est résolu DANS la
        société courante — un id d'une autre société est introuvable (404). Le
        recalcul du chemin matérialisé de tout le sous-arbre est délégué à
        `services.move_folder` (refus de cycle / cabinet différent → 400)."""
        folder = self.get_object()
        raw_parent = request.data.get('parent', None)
        new_parent = None
        if raw_parent not in (None, '', 'null'):
            new_parent = self._resolve_company_folder(raw_parent)
            if new_parent is None:
                return Response(
                    {'parent': 'Dossier parent inconnu.'},
                    status=status.HTTP_404_NOT_FOUND)
        try:
            services.move_folder(folder, new_parent)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        folder.refresh_from_db()
        data = FolderSerializer(folder, context={'request': request}).data
        return Response(data)


class DocumentViewSet(TenantMixin, viewsets.ModelViewSet):
    """Documents logiques (conteneurs versionnés) d'une société."""
    queryset = Document.objects.select_related('folder', 'created_by').all()
    serializer_class = DocumentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'created_at', 'updated_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        folder = self.request.query_params.get('folder')
        if folder:
            qs = qs.filter(folder_id=folder)
        return qs

    def perform_create(self, serializer):
        # company + created_by posés côté serveur.
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='deplacer')
    def deplacer(self, request, pk=None):
        """Déplace ce document dans un autre dossier (déplacement scopé société).

        Body : `{"folder": <id>}`. Le document source est company-scopé via
        `get_object()` (404 cross-société). Le dossier cible est résolu DANS la
        société courante — un id d'une autre société est introuvable (404). La
        société du document n'est jamais modifiée (posée côté serveur)."""
        document = self.get_object()
        raw_folder = request.data.get('folder', None)
        if raw_folder in (None, '', 'null'):
            return Response(
                {'folder': 'Le dossier cible est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        new_folder = (Folder.objects
                      .filter(company=request.user.company)
                      .filter(pk=raw_folder).first())
        if new_folder is None:
            return Response(
                {'folder': 'Dossier inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            services.move_document(document, new_folder)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        document.refresh_from_db()
        data = DocumentSerializer(document, context={'request': request}).data
        return Response(data)


class DocumentVersionViewSet(TenantMixin, viewsets.ModelViewSet):
    """Versions d'un document. Le numéro de version et `uploaded_by` sont posés
    côté serveur via `services.add_version` ; `checksum` permet la dédup."""
    queryset = DocumentVersion.objects.select_related(
        'document', 'uploaded_by').all()
    serializer_class = DocumentVersionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        return qs

    def perform_create(self, serializer):
        # Numéro de version auto-incrémenté + company/uploaded_by côté serveur.
        document = serializer.validated_data['document']
        v = serializer.validated_data
        instance = services.add_version(
            document,
            file_key=v['file_key'],
            company=self.request.user.company,
            filename=v.get('filename', ''),
            size=v.get('size', 0),
            mime=v.get('mime', ''),
            checksum=v.get('checksum', ''),
            uploaded_by=self.request.user,
        )
        serializer.instance = instance
