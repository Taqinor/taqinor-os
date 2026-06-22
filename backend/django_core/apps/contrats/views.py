"""Vues de la Gestion des contrats (scopées société, accès admin/responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; l'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``).
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Contrat, PartieContrat
from .serializers import ContratSerializer, PartieContratSerializer


class _ContratsBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ContratViewSet(_ContratsBaseViewSet):
    """Contrats de la société (CLM). Recherche par référence/objet."""
    queryset = Contrat.objects.all()
    serializer_class = ContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet']
    ordering_fields = ['date_debut', 'date_fin', 'montant', 'id']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class PartieContratViewSet(_ContratsBaseViewSet):
    """Parties/signataires des contrats de la société.

    Société posée côté serveur (``TenantMixin.perform_create``) ; le contrat
    rattaché est validé même société par le sérialiseur. Filtrable par
    ``?contrat=<id>`` et recherchable par nom/email.
    """
    queryset = PartieContrat.objects.all()
    serializer_class = PartieContratSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email']
    ordering_fields = ['ordre', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        contrat_id = self.request.query_params.get('contrat')
        if contrat_id:
            qs = qs.filter(contrat_id=contrat_id)
        return qs
