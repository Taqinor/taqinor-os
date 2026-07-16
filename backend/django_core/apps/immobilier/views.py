"""Vues du module Immobilier (scopées société via ``TenantMixin``).

Aucune permission fine dédiée (comme ``apps.flotte``) : ``IsAuthenticated``
(défaut DRF global) suffit pour ce premier lot — une gate fine pourra être
ajoutée plus tard sans changer la forme des endpoints.
"""
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import TenantMixin

from .models import Batiment, Local, Locataire, Niveau, Site
from .serializers import (
    BatimentSerializer, LocalSerializer, LocataireSerializer, NiveauSerializer,
    SiteSerializer,
)


class _ImmobilierBaseViewSet(TenantMixin, viewsets.ModelViewSet):
    """Base commune : société scopée (get_queryset + perform_create/update)."""
    pass


class SiteViewSet(_ImmobilierBaseViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'ville']
    ordering_fields = ['nom', 'date_creation']


class BatimentViewSet(_ImmobilierBaseViewSet):
    queryset = Batiment.objects.select_related('site').all()
    serializer_class = BatimentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom']

    def get_queryset(self):
        qs = super().get_queryset()
        site_id = self.request.query_params.get('site')
        if site_id:
            qs = qs.filter(site_id=site_id)
        return qs


class NiveauViewSet(_ImmobilierBaseViewSet):
    queryset = Niveau.objects.select_related('batiment').all()
    serializer_class = NiveauSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['numero', 'ordre']

    def get_queryset(self):
        qs = super().get_queryset()
        batiment_id = self.request.query_params.get('batiment')
        if batiment_id:
            qs = qs.filter(batiment_id=batiment_id)
        return qs


class LocalViewSet(_ImmobilierBaseViewSet):
    queryset = Local.objects.select_related('niveau', 'niveau__batiment').all()
    serializer_class = LocalSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference']
    ordering_fields = ['reference']

    def get_queryset(self):
        qs = super().get_queryset()
        niveau_id = self.request.query_params.get('niveau')
        batiment_id = self.request.query_params.get('batiment')
        site_id = self.request.query_params.get('site')
        statut = self.request.query_params.get('statut')
        if niveau_id:
            qs = qs.filter(niveau_id=niveau_id)
        if batiment_id:
            qs = qs.filter(niveau__batiment_id=batiment_id)
        if site_id:
            qs = qs.filter(niveau__batiment__site_id=site_id)
        if statut:
            qs = qs.filter(statut=statut)
        return qs


class LocataireViewSet(_ImmobilierBaseViewSet):
    """NTPRO2 — Locataires (personnes/sociétés), distincts du CRM."""
    queryset = Locataire.objects.all()
    serializer_class = LocataireSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'cin', 'ice']
    ordering_fields = ['nom', 'date_creation']

    def perform_create(self, serializer):
        from . import services
        locataire = serializer.save(company=self.request.user.company)
        # Best-effort : relie à un crm.Client existant sans jamais en créer un
        # nouveau (NTPRO2). Un échec de résolution ne bloque jamais la création
        # du locataire.
        try:
            services.resolve_client_ventes_for_locataire(locataire)
        except Exception:
            pass
        return locataire

    @action(detail=True, methods=['post'], url_path='resolve-client')
    def resolve_client(self, request, pk=None):
        """Relance la résolution vers un ``crm.Client`` existant (idempotent)."""
        from . import services
        locataire = self.get_object()
        client_id = services.resolve_client_ventes_for_locataire(locataire)
        return Response({'client_ventes_id': client_id})
