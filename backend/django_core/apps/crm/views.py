from rest_framework import viewsets, filters
from authentication.mixins import TenantMixin
from .models import Client, Lead
from .serializers import ClientSerializer, LeadSerializer
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class ClientViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'prenom', 'email', 'telephone']
    ordering_fields = ['nom', 'date_creation']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class LeadViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'prenom', 'societe', 'email', 'telephone', 'ville']
    ordering_fields = ['nom', 'date_creation', 'stage']
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        # Optional filters: ?stage=NEW  &  ?source=odoo_import_test
        stage = self.request.query_params.get('stage')
        source = self.request.query_params.get('source')
        if stage:
            qs = qs.filter(stage=stage)
        if source:
            qs = qs.filter(source=source)
        return qs

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]
