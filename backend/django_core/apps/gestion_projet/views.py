"""Vues de la Gestion de projet (toutes scopées société, admin-gated).

L'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``). Les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société côté serveur ; le ``responsable`` reçu est
validé comme appartenant à la même société.
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import Projet, ProjetChantier
from .serializers import ProjetChantierSerializer, ProjetSerializer


class _GestionProjetBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class ProjetViewSet(_GestionProjetBaseViewSet):
    """Projets multi-chantier de la société. Recherche par code/nom.

    ``company`` est posée côté serveur par le ``TenantMixin`` ; le
    ``responsable`` provient du corps validé du sérialiseur.
    """
    queryset = Projet.objects.select_related('responsable').all()
    serializer_class = ProjetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom', 'description']
    ordering_fields = ['code', 'nom', 'statut', 'date_debut', 'id']

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs


class ProjetChantierViewSet(_GestionProjetBaseViewSet):
    """Rattachements chantier ↔ projet (liens lâches)."""
    queryset = ProjetChantier.objects.select_related('projet').all()
    serializer_class = ProjetChantierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        return qs
