from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from .models import Client, Lead
from .serializers import ClientSerializer, LeadSerializer, LeadActivitySerializer
from . import activity
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

    def destroy(self, request, *args, **kwargs):
        # Un client avec des devis est PROTÉGÉ (pas de cascade) : message
        # français clair au lieu d'un 500 silencieux.
        from django.db.models import ProtectedError
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': "Ce client a des devis liés — supprimez ou "
                           "réassignez ses devis d'abord."},
                status=status.HTTP_409_CONFLICT,
            )


class LeadViewSet(TenantMixin, viewsets.ModelViewSet):
    """Leads + historique « chatter » (journal automatique + notes manuelles).

    L'utilisateur acteur et la société viennent toujours de la requête côté
    serveur — jamais du corps envoyé par le navigateur.
    """
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

    def perform_create(self, serializer):
        super().perform_create(serializer)
        activity.log_creation(serializer.instance, self.request.user)

    def perform_update(self, serializer):
        # Snapshot avant écriture pour journaliser ancien → nouveau.
        old = Lead.objects.get(pk=serializer.instance.pk)
        super().perform_update(serializer)
        activity.log_changes(old, serializer.instance, self.request.user)

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['historique']:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['noter']:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    @action(detail=True, methods=['get'], url_path='historique',
            permission_classes=[IsAnyRole])
    def historique(self, request, pk=None):
        """Timeline chatter du lead (auto + notes), du plus récent au plus ancien."""
        lead = self.get_object()
        return Response(
            LeadActivitySerializer(lead.activites.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path='noter',
            permission_classes=[IsResponsableOrAdmin])
    def noter(self, request, pk=None):
        """Note manuelle (appel, commentaire…) — auteur pris de la requête."""
        lead = self.get_object()
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'body': 'Note vide.'},
                            status=status.HTTP_400_BAD_REQUEST)
        act = activity.log_note(lead, request.user, body)
        return Response(LeadActivitySerializer(act).data,
                        status=status.HTTP_201_CREATED)
