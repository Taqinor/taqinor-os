"""FG66 / DC36 — Vue du kit / nomenclature (BOM) vendable.

Un kit est un en-tête + des composants (produits du catalogue). DC36 : le kit
ne porte aucun prix / marque / TVA propre ; l'action ``exploser`` le décompose
en lignes composant avec prix/TVA/marque LUS sur chaque ``Produit`` au vol.
Multi-tenant : querysets filtrés par société + ``company`` forcée côté serveur
(TenantMixin)."""
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from core.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsAdminRole, HasPermissionOrLegacy

from ..models import KitProduit
from ..serializers import KitProduitSerializer

READ_ACTIONS = ['list', 'retrieve', 'exploser']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class KitProduitViewSet(TenantMixin, viewsets.ModelViewSet):
    queryset = KitProduit.objects.all().prefetch_related('composants__produit')
    serializer_class = KitProduitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'sku', 'description']
    ordering = ['nom']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        return [IsAdminRole()]

    @action(detail=True, methods=['get'], url_path='exploser')
    def exploser(self, request, *args, **kwargs):
        """Explose le kit en lignes composant (param ``quantite`` ≥ 1, défaut 1).
        Prix / TVA / marque dérivés des produits (DC36). Le prix d'achat n'est
        jamais exposé."""
        from ..services import exploser_kit
        kit = self.get_object()
        try:
            quantite = float(request.query_params.get('quantite', 1) or 1)
        except (TypeError, ValueError):
            quantite = 1
        if quantite <= 0:
            quantite = 1
        return Response({
            'kit_id': kit.id,
            'kit_nom': kit.nom,
            'quantite_kit': quantite,
            'lignes': exploser_kit(kit, quantite),
        })
