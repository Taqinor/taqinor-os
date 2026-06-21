"""Vues du module Gestion de flotte (toutes scopées société).

La flotte est INTERNE. Chaque viewset filtre par ``request.user.company``
(``TenantMixin``) et pose la société côté serveur ; aucune société n'est jamais
acceptée du corps de requête (multi-tenant).
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .models import EnginRoulant, Vehicule
from .serializers import EnginRoulantSerializer, VehiculeSerializer

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


class EnginRoulantViewSet(_FlotteBaseViewSet):
    """Engins roulants suivis au compteur d'heures (FLOTTE4). Filtrable par
    type/statut, recherche par désignation/marque/modèle."""
    queryset = EnginRoulant.objects.all()
    serializer_class = EnginRoulantSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'marque', 'modele']
    ordering_fields = ['nom', 'compteur_heures', 'statut', 'date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        type_engin = params.get('type_engin')
        if type_engin:
            qs = qs.filter(type_engin=type_engin)
        return qs
