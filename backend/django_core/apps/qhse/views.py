"""Vues QHSE (scopées société, accès Administrateur/Responsable).

Les viewsets filtrent par ``request.user.company`` (TenantMixin) et posent la
société côté serveur ; la non-conformité enregistre aussi son signaleur
(``signale_par``) côté serveur.
"""
from rest_framework import filters, viewsets

from authentication.mixins import TenantMixin
from authentication.permissions import IsResponsableOrAdmin

from .models import (
    ActionCorrectivePreventive, NonConformite, PlanInspectionModele,
    PointControleModele,
)
from .serializers import (
    ActionCorrectivePreventiveSerializer, NonConformiteSerializer,
    PlanInspectionModeleSerializer, PointControleModeleSerializer,
)


class _QhseBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base : société scopée + accès Administrateur/Responsable uniquement."""
    permission_classes = [IsResponsableOrAdmin]


class NonConformiteViewSet(_QhseBaseViewSet):
    """Fiches de non-conformité (QHSE9). Recherche par référence/titre/origine."""
    queryset = NonConformite.objects.all()
    serializer_class = NonConformiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'titre', 'origine']
    ordering_fields = ['id', 'date_detection', 'date_creation']

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            signale_par=self.request.user)


class ActionCorrectivePreventiveViewSet(_QhseBaseViewSet):
    """Actions correctives / préventives (CAPA — QHSE10)."""
    queryset = ActionCorrectivePreventive.objects.select_related(
        'non_conformite').all()
    serializer_class = ActionCorrectivePreventiveSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'cause_racine']
    ordering_fields = ['id', 'echeance', 'date_creation']


class PlanInspectionModeleViewSet(_QhseBaseViewSet):
    """Modèles de plan d'inspection (ITP — QHSE2). Recherche par code/nom."""
    queryset = PlanInspectionModele.objects.all()
    serializer_class = PlanInspectionModeleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'nom', 'description']
    ordering_fields = ['id', 'nom', 'date_creation']


class PointControleModeleViewSet(_QhseBaseViewSet):
    """Points de contrôle d'un modèle de plan d'inspection (ITP — QHSE2)."""
    queryset = PointControleModele.objects.select_related('plan').all()
    serializer_class = PointControleModeleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['intitule', 'phase', 'description']
    ordering_fields = ['id', 'ordre', 'date_creation']
