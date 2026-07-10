from core.viewsets import CompanyScopedModelViewSet
from ..models import ConditionnementProduit
from ..serializers import ConditionnementProduitSerializer
from authentication.permissions import IsAnyRole, HasPermissionOrLegacy

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.

READ_ACTIONS = ['list', 'retrieve']


class ConditionnementProduitViewSet(CompanyScopedModelViewSet):
    """XSTK15 — conditionnements d'achat (touret/carton…) d'un produit,
    convertis vers `Produit.unite_stock` à la réception."""
    queryset = ConditionnementProduit.objects.select_related('produit').all()
    serializer_class = ConditionnementProduitSerializer

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
