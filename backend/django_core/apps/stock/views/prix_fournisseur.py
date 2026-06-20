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


class PrixFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """N17 — prix d'achat multi-fournisseurs par SKU (INTERNE). Lecture tout
    rôle, écriture stock_modifier. `company` posé serveur ; produit/fournisseur
    doivent appartenir à la société."""
    queryset = PrixFournisseur.objects.select_related(
        'produit', 'fournisseur').all()
    serializer_class = PrixFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['prix_achat', 'date_dernier_achat']
    ordering = ['prix_achat']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [HasPermissionOrLegacy('stock_modifier')()]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        return qs

    def _check_company(self, serializer):
        company = self.request.user.company
        produit = serializer.validated_data.get('produit')
        fournisseur = serializer.validated_data.get('fournisseur')
        from rest_framework.exceptions import ValidationError
        if produit is not None and produit.company_id != getattr(
                company, 'id', None):
            raise ValidationError({'produit': 'Produit hors de votre entreprise.'})
        if fournisseur is not None and fournisseur.company_id != getattr(
                company, 'id', None):
            raise ValidationError(
                {'fournisseur': 'Fournisseur hors de votre entreprise.'})

    def perform_create(self, serializer):
        self._check_company(serializer)
        serializer.save(company=self.request.user.company)

    def perform_update(self, serializer):
        self._check_company(serializer)
        serializer.save(company=self.request.user.company)
