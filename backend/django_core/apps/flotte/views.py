"""Vues du module Gestion de flotte (toutes scopées société, admin-gated).

La flotte est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``). Chaque
viewset filtre par ``request.user.company`` (``TenantMixin``) et pose la société
côté serveur ; aucune société n'est jamais acceptée du corps de requête.
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Vehicule
from .serializers import VehiculeSerializer


class _FlotteBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class VehiculeViewSet(_FlotteBaseViewSet):
    """Véhicules du parc (FLOTTE2). Filtrable par énergie/statut/type,
    recherche par immatriculation/marque/modèle."""
    queryset = Vehicule.objects.select_related('conducteur').all()
    serializer_class = VehiculeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['immatriculation', 'marque', 'modele']
    ordering_fields = ['immatriculation', 'kilometrage', 'statut',
                       'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        energie = params.get('energie')
        if energie:
            qs = qs.filter(energie=energie)
        type_vehicule = params.get('type_vehicule')
        if type_vehicule:
            qs = qs.filter(type_vehicule=type_vehicule)
        return qs
