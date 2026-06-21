"""Vues des Ressources humaines (toutes scopées société, admin-gated).

Le module RH est INTERNE : aucune donnée n'est exposée côté client. L'accès est
réservé au palier Administrateur/Responsable (``IsResponsableOrAdmin``). Les
viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la société
côté serveur ; le ``cout_horaire`` (paie/marge) ne quitte jamais cette API.
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Departement, DossierEmploye
from .serializers import DepartementSerializer, DossierEmployeSerializer


class _RhBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class DepartementViewSet(_RhBaseViewSet):
    """Départements de la société. Recherche par nom/code."""
    queryset = Departement.objects.all()
    serializer_class = DepartementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'code']
    ordering_fields = ['nom']


class DossierEmployeViewSet(_RhBaseViewSet):
    """Dossiers employés (DC29). Recherche par matricule/nom/prénom."""
    queryset = DossierEmploye.objects.select_related('departement', 'user').all()
    serializer_class = DossierEmployeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['matricule', 'nom', 'prenom', 'cin', 'email']
    ordering_fields = ['nom', 'prenom', 'matricule', 'date_embauche']
