from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework.parsers import JSONParser
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


class CategorieViewSet(CompanyScopedModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering = ['nom']
    # YAPIC2 — whitelist explicite (jamais '__all__') : tri arbitraire par
    # colonne non indexée sinon possible.
    ordering_fields = ['nom', 'ordre', 'type_equipement']

    parser_classes = [JSONParser]

    def get_queryset(self):
        # ERR-QAH-STOCK-CATEGORIES-COMPTE-ZERO — nombre de produits non
        # archivés par catégorie, en UNE requête (pas de N+1 sur la liste).
        from django.db.models import Q
        return super().get_queryset().annotate(
            nb_produits_annot=Count(
                'produits', filter=Q(produits__is_archived=False)))

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def destroy(self, request, *args, **kwargs):
        """ASTK82 — refuse (400) de supprimer une catégorie portant des
        produits (actifs OU archivés) : la FK est ``SET_NULL``, donc sans cette
        garde chaque produit serait dé-catégorisé en silence (son rôle devis
        retombant sur les mots-clés du nom) et les profils saisonniers de la
        catégorie supprimés en cascade."""
        categorie = self.get_object()
        nb = Produit.objects.filter(
            company=request.user.company, categorie=categorie).count()
        if nb:
            mot = 'produit' if nb == 1 else 'produits'
            return Response(
                {'detail': (f'Catégorie utilisée par {nb} {mot} : '
                            'réaffectez-les avant de la supprimer.')},
                status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)
