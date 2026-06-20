from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from authentication.mixins import TenantMixin  # noqa: F401
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


class EmplacementStockViewSet(TenantMixin, viewsets.ModelViewSet):
    """N15 — emplacements de stock (dépôt principal + camionnette amorcés au
    premier accès). Lecture tout rôle, écriture admin. Le principal ne peut être
    ni supprimé ni archivé ; un emplacement détenant du stock ne peut pas être
    supprimé (transférez d'abord)."""
    queryset = EmplacementStock.objects.all()
    serializer_class = EmplacementStockSerializer
    ordering = ['-is_principal', 'ordre', 'nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminRole()]

    def list(self, request, *args, **kwargs):
        from ..services import ensure_emplacements
        if request.user.company_id:
            ensure_emplacements(request.user.company)
        return super().list(request, *args, **kwargs)

    def _holds_stock(self, emplacement):
        return emplacement.stocks.filter(quantite__gt=0).exists()

    def destroy(self, request, *args, **kwargs):
        emp = self.get_object()
        if emp.is_principal:
            return Response(
                {'detail': 'Le dépôt principal ne peut pas être supprimé.'},
                status=status.HTTP_400_BAD_REQUEST)
        if self._holds_stock(emp):
            return Response(
                {'detail': 'Cet emplacement détient du stock — transférez-le '
                           'avant de le supprimer.'},
                status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)
