from django.db.models import ProtectedError, Count, Min, Max
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from .models import Produit, Categorie, Fournisseur, MouvementStock
from .serializers import (
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
)
from authentication.permissions import (
    IsAnyRole,
    IsResponsableOrAdmin,
    IsAdminRole,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class ProduitViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Produit.objects.select_related(
        'categorie', 'fournisseur'
    ).all()
    serializer_class = ProduitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'sku', 'description', 'categorie__nom']
    ordering_fields = [
        'nom', 'quantite_stock', 'prix_vente', 'date_creation'
    ]
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action in ('destroy', 'force_delete'):
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('show_archived') == 'true':
            return qs.annotate(
                nb_mouvements=Count('mouvements'),
                premiere_date_mouvement=Min('mouvements__date'),
                derniere_date_mouvement=Max('mouvements__date'),
            )
        if self.action in ('force_delete', 'unarchive'):
            return qs  # archived products must be visible for these actions
        return qs.filter(is_archived=False)

    def destroy(self, request, *args, **kwargs):
        produit = self.get_object()
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            nb = produit.mouvements.count()
            produit.is_archived = True
            produit.save(update_fields=['is_archived'])
            return Response(
                {
                    'archived': True,
                    'detail': (
                        f'Ce produit a été archivé car il possède {nb} '
                        f'mouvement(s) de stock. L\'historique est conservé.'
                    ),
                    'nb_mouvements': nb,
                },
                status=status.HTTP_200_OK,
            )

    @action(detail=True, methods=['patch'], url_path='unarchive')
    def unarchive(self, request, *args, **kwargs):
        produit = self.get_object()
        if not produit.is_archived:
            return Response(
                {'detail': 'Ce produit n\'est pas archivé.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        produit.is_archived = False
        produit.save(update_fields=['is_archived'])
        serializer = self.get_serializer(produit)
        return Response(serializer.data)

    @action(detail=True, methods=['delete'], url_path='force-delete')
    def force_delete(self, request, *args, **kwargs):
        produit = self.get_object()
        if not produit.is_archived:
            return Response(
                {
                    'detail': (
                        'Seuls les produits archivés peuvent être '
                        'supprimés définitivement.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        nb = produit.mouvements.count()
        produit.mouvements.all().delete()
        produit.delete()
        return Response(
            {
                'detail': (
                    f'Produit et {nb} mouvement(s) supprimé(s) définitivement.'
                )
            },
            status=status.HTTP_200_OK,
        )


class CategorieViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


class FournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'email', 'contact_personne']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]


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
            return [IsResponsableOrAdmin()]
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
        produit = serializer.validated_data['produit']
        user = self.request.user
        # Reject cross-tenant produit references before touching stock.
        if user.company_id and produit.company_id != user.company_id:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Produit hors de votre entreprise.")
        produit.refresh_from_db()
        qte = serializer.validated_data['quantite']
        type_mv = serializer.validated_data['type_mouvement']
        qte_avant = produit.quantite_stock
        if type_mv == MouvementStock.TypeMouvement.ENTREE:
            qte_apres = qte_avant + qte
        elif type_mv == MouvementStock.TypeMouvement.SORTIE:
            qte_apres = qte_avant - qte
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
