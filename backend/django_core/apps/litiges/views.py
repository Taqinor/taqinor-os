"""Vues des Réclamations & litiges (scopées société, accès admin/responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société + le créateur côté serveur (jamais du corps de requête).
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Reclamation
from .serializers import ReclamationSerializer


class _LitigesBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ReclamationViewSet(_LitigesBaseViewSet):
    """Réclamations & litiges. Recherche par référence/objet/description."""
    queryset = Reclamation.objects.select_related('created_by').all()
    serializer_class = ReclamationSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet', 'description']
    ordering_fields = ['id', 'gravite', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
