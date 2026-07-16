"""Vues du module Hôtellerie & restauration.

Les viewsets filtrent par ``request.user.company`` (``TenantMixin``) et posent
la société côté serveur (jamais du corps de requête). Lecture ouverte à tout
rôle authentifié (``IsAnyRole``) ; écriture réservée Responsable/Admin
(``IsResponsableOrAdmin``), sauf actions explicitement ouvertes (ex. tâches de
housekeeping assignées à l'utilisateur courant).
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from .models import Chambre, TypeChambre
from .serializers import ChambreSerializer, TypeChambreSerializer

READ_ACTIONS = ['list', 'retrieve']


class TypeChambreViewSet(TenantMixin, viewsets.ModelViewSet):
    """Catégories de chambre (Standard/Suite/Riad-suite…), CRUD scopé société."""
    queryset = TypeChambre.objects.all()
    serializer_class = TypeChambreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle']
    ordering_fields = ['libelle', 'capacite_max']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class ChambreViewSet(TenantMixin, viewsets.ModelViewSet):
    """Chambres/unités, CRUD scopé société. Filtre ``?statut=``."""
    queryset = Chambre.objects.select_related('type_chambre').all()
    serializer_class = ChambreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero', 'nom', 'etage']
    ordering_fields = ['numero', 'statut']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs
