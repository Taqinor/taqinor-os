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


class MouvementStockViewSet(viewsets.ModelViewSet):
    queryset = MouvementStock.objects.select_related(
        'produit', 'created_by'
    ).all()
    serializer_class = MouvementStockSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['produit__nom', 'reference', 'note']
    ordering_fields = ['date', 'type_mouvement', 'quantite']
    ordering = ['-date']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action == 'create':
            return [HasPermissionOrLegacy('stock_mouvement')()]
        else:
            return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            # Direct company filter + produit__company belt-and-braces guard
            # against cross-tenant produit references slipping in.
            return qs.filter(company=user.company, produit__company=user.company)
        if user.is_superuser:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied, ValidationError
        produit = serializer.validated_data['produit']
        user = self.request.user
        # Reject cross-tenant produit references before touching stock.
        if user.company_id and produit.company_id != user.company_id:
            raise PermissionDenied("Produit hors de votre entreprise.")
        qte = serializer.validated_data['quantite']
        type_mv = serializer.validated_data['type_mouvement']
        # ERR10 — la quantité d'une ENTREE/SORTIE doit être strictement
        # positive : on n'accepte ni 0, ni négatif (un négatif transformerait
        # silencieusement une SORTIE en augmentation de stock — corruption /
        # fraude). Les ajustements/transferts portent leur propre logique.
        if type_mv in (
            MouvementStock.TypeMouvement.ENTREE,
            MouvementStock.TypeMouvement.SORTIE,
        ) and (qte is None or qte <= 0):
            raise ValidationError(
                {'quantite': 'La quantité doit être strictement positive.'})
        # ERR23 — section critique atomique + verrou de ligne produit pour que
        # des SORTIEs concurrentes ne perdent pas de mise à jour et ne
        # corrompent pas les colonnes d'audit quantite_avant/quantite_apres.
        with transaction.atomic():
            produit = (Produit.objects.select_for_update()
                       .get(pk=produit.pk))
            qte_avant = produit.quantite_stock
            if type_mv == MouvementStock.TypeMouvement.ENTREE:
                qte_apres = qte_avant + qte
            elif type_mv == MouvementStock.TypeMouvement.SORTIE:
                qte_apres = qte_avant - qte
                # ERR10 — une SORTIE ne peut jamais faire descendre le stock
                # sous zéro (garde plancher) : refus explicite en 400.
                if qte_apres < 0:
                    raise ValidationError(
                        {'quantite': (
                            'Stock insuffisant : la sortie dépasse le stock '
                            f'disponible ({qte_avant}).')})
            else:
                qte_apres = qte
            serializer.save(
                created_by=user,
                company=produit.company,
                quantite_avant=qte_avant,
                quantite_apres=qte_apres,
            )
            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])
