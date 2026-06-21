"""Vues du module Gestion de flotte (toutes scopées société).

La flotte est INTERNE. Chaque viewset filtre par ``request.user.company``
(``TenantMixin``) et pose la société côté serveur ; aucune société n'est jamais
acceptée du corps de requête (multi-tenant).
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .models import Vehicule
from .serializers import VehiculeSerializer

READ_ACTIONS = ['list', 'retrieve']


class _FlotteBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée (TenantMixin). Lecture tout rôle, écriture
    responsable/admin."""

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class VehiculeViewSet(_FlotteBaseViewSet):
    """Véhicules immatriculés du parc (FLOTTE2). Filtrable par énergie/statut,
    recherche par immatriculation/marque/modèle."""
    queryset = Vehicule.objects.all()
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
        return qs
