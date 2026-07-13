from rest_framework import filters
from core.viewsets import CompanyScopedModelViewSet
from ..models import FicheTechnique
from ..serializers import FicheTechniqueSerializer
from authentication.permissions import (
    IsAnyRole,
    IsAdminRole,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class FicheTechniqueViewSet(CompanyScopedModelViewSet):
    """DC35 / FG254 — fiches techniques (datasheets) rattachées aux produits.

    Multi-tenant : le queryset est filtré sur la société du demandeur
    (``TenantMixin``) et ``company`` est forcé serveur dans ``perform_create``
    — jamais accepté depuis le corps de la requête. Lecture tout rôle, écriture
    selon la permission stock, suppression admin."""
    queryset = FicheTechnique.objects.select_related('produit').all()
    serializer_class = FicheTechniqueSerializer
    filter_backends = [filters.OrderingFilter]
    ordering = ['-date_mise_a_jour']
    # YAPIC2 — whitelist explicite (jamais '__all__').
    ordering_fields = ['date_creation', 'date_mise_a_jour', 'pmax_wc']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            return [HasPermissionOrLegacy('stock_modifier')()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        return qs
