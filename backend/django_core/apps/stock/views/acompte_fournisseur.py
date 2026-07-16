from django.db import transaction  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from ..models import AcompteFournisseur
from ..serializers import AcompteFournisseurSerializer
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class AcompteFournisseurViewSet(CompanyScopedModelViewSet):
    """XPUR8 — acomptes/avances fournisseur sur BCF. Imputés automatiquement
    (idempotent) sur la première facture du BCF via
    `services.facturer_reception` → `imputer_acomptes_bcf`. Lecture tout
    rôle ; écriture responsable/admin. `company` posée côté serveur."""
    queryset = AcompteFournisseur.objects.select_related(
        'bon_commande', 'facture_imputee', 'created_by').all()
    serializer_class = AcompteFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_versement', 'date_creation', 'montant']
    ordering = ['-date_versement', '-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        bcf_id = self.request.query_params.get('bon_commande')
        if bcf_id:
            qs = qs.filter(bon_commande_id=bcf_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
