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


class PaiementFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """G5 — Paiements fournisseur (règlements). Lecture + création/suppression ;
    chaque écriture recalcule le statut de la facture. company posée serveur."""
    queryset = PaiementFournisseur.objects.select_related(
        'facture', 'created_by').all()
    serializer_class = PaiementFournisseurSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_paiement', 'date_creation', 'montant']
    ordering = ['-date_paiement', '-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        facture_id = self.request.query_params.get('facture')
        if facture_id:
            qs = qs.filter(facture_id=facture_id)
        return qs

    def perform_create(self, serializer):
        from ..services import recompute_facture_fournisseur_statut
        with transaction.atomic():
            paiement = serializer.save(company=self.request.user.company,
                                       created_by=self.request.user)
            paiement.facture.refresh_from_db()
            recompute_facture_fournisseur_statut(paiement.facture)

    def perform_destroy(self, instance):
        from ..services import recompute_facture_fournisseur_statut
        facture = instance.facture
        with transaction.atomic():
            instance.delete()
            facture.refresh_from_db()
            recompute_facture_fournisseur_statut(facture)
