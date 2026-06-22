"""Vues de la Gestion de projet (toutes scopées société, admin-gated).

L'accès est réservé au palier Administrateur/Responsable
(``IsResponsableOrAdmin``). Les viewsets filtrent par ``request.user.company``
(TenantMixin) et posent la société côté serveur ; le ``responsable`` reçu est
validé comme appartenant à la même société.
"""
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from . import selectors
from .models import Projet, ProjetChantier, ProjetLien
from .serializers import (
    ProjetChantierSerializer,
    ProjetLienSerializer,
    ProjetSerializer,
)


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

    @action(detail=True, methods=['get'])
    def liens(self, request, pk=None):
        """Liens du projet ENRICHIS via les sélecteurs des apps cibles.

        Pour chaque lien : libellé frais quand l'app cible expose un sélecteur
        (``source='live'``), sinon le libellé stocké (``source='stored'``). La
        société est garantie par ``get_object`` (queryset scopé société).
        """
        projet = self.get_object()
        return Response(selectors.liens_enrichis(projet))


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


class ProjetLienViewSet(_GestionProjetBaseViewSet):
    """Liens projet → devis / facture / ticket / achat (références lâches).

    ``company`` est posée côté serveur (TenantMixin) ; le ``projet`` reçu est
    validé même-société par le sérialiseur. Filtre optionnel ``?projet=<id>`` et
    ``?type_cible=<type>``.
    """
    queryset = ProjetLien.objects.select_related('projet').all()
    serializer_class = ProjetLienSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['id']

    def get_queryset(self):
        qs = super().get_queryset()
        projet = self.request.query_params.get('projet')
        if projet:
            qs = qs.filter(projet_id=projet)
        type_cible = self.request.query_params.get('type_cible')
        if type_cible:
            qs = qs.filter(type_cible=type_cible)
        return qs
