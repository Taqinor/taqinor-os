"""Vues de la Gestion documentaire (GED) — toutes scopées société.

L'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``). Les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société côté serveur ; ``created_by`` est posé côté
serveur sur les documents.
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Document, DocumentVersion, Dossier
from .serializers import (
    DocumentSerializer, DocumentVersionSerializer, DossierSerializer,
)


class _GedBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class DossierViewSet(_GedBaseViewSet):
    """Dossiers arborescents (GED2) — chemin matérialisé côté serveur."""
    queryset = Dossier.objects.select_related('parent').all()
    serializer_class = DossierSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'chemin']
    ordering_fields = ['nom', 'chemin']


class DocumentViewSet(_GedBaseViewSet):
    """Documents logiques (GED3). ``created_by`` posé côté serveur."""
    queryset = Document.objects.select_related('dossier', 'created_by').all()
    serializer_class = DocumentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'description']
    ordering_fields = ['titre', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class DocumentVersionViewSet(_GedBaseViewSet):
    """Versions de document (GED3) — pointeur MinIO + checksum."""
    queryset = DocumentVersion.objects.select_related('document').all()
    serializer_class = DocumentVersionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero_version', 'date_creation']
