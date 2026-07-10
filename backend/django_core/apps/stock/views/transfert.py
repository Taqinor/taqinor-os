from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class TransfertStockViewSet(CompanyScopedModelViewSet):
    """N15 — transferts de stock entre emplacements (le « transfer record »).

    Lecture seule + création. La création passe par le service `transfer_stock`
    (validation + atomicité), jamais par un save direct. Le total
    `Produit.quantite_stock` n'est jamais modifié par un transfert."""
    queryset = TransfertStock.objects.select_related(
        'produit', 'source', 'destination', 'created_by').all()
    serializer_class = TransfertStockSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['produit__nom', 'note']
    ordering_fields = ['date', 'quantite']
    ordering = ['-date']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action == 'create':
            return [HasPermissionOrLegacy('stock_mouvement')()]
        return [IsAdminRole()]

    def create(self, request, *args, **kwargs):
        from ..services import transfer_stock
        try:
            transfert = transfer_stock(
                company=request.user.company, user=request.user,
                produit_id=request.data.get('produit'),
                source_id=request.data.get('source'),
                destination_id=request.data.get('destination'),
                quantite=request.data.get('quantite'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(transfert).data,
                        status=status.HTTP_201_CREATED)
