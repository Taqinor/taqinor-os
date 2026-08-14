"""Vues du module « ecommerce_connect » (NTRET18/19) — configuration des
connexions + déclenchement manuel de la synchro catalogue (le Celery beat
périodique est hors périmètre de cette lane, voir ``shopify.py``)."""
from rest_framework.decorators import action
from rest_framework.response import Response

from core.viewsets import CompanyScopedModelViewSet

from .models import CommandeSync, ConnexionEcommerce, ProduitSync
from .serializers import (
    CommandeSyncSerializer, ConnexionEcommerceSerializer, ProduitSyncSerializer,
)


class ConnexionEcommerceViewSet(CompanyScopedModelViewSet):
    """Configuration (SANS secret) d'une connexion Shopify/WooCommerce."""

    queryset = ConnexionEcommerce.objects.all()
    serializer_class = ConnexionEcommerceSerializer

    @action(detail=True, methods=['post'], url_path='sync-catalogue')
    def sync_catalogue(self, request, pk=None):
        """Déclenchement MANUEL de la synchro catalogue → plateforme.

        No-op total sans clé API configurée (``shopify.is_configured()``/
        ``woocommerce.is_configured()``) — jamais d'appel réseau ni
        d'exception dans ce cas."""
        connexion = self.get_object()
        if connexion.plateforme == ConnexionEcommerce.Plateforme.SHOPIFY:
            from . import shopify
            resultat = shopify.sync_catalogue(connexion.company)
        else:
            from . import woocommerce
            resultat = woocommerce.sync_catalogue(connexion.company)
        return Response(resultat)


class ProduitSyncViewSet(CompanyScopedModelViewSet):
    """Opt-in « vendable en ligne » par produit (mapping ERP ↔ externe)."""

    queryset = ProduitSync.objects.select_related('connexion').all()
    serializer_class = ProduitSyncSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        connexion_id = self.request.query_params.get('connexion')
        if connexion_id:
            qs = qs.filter(connexion_id=connexion_id)
        return qs


class CommandeSyncViewSet(CompanyScopedModelViewSet):
    """Journal LECTURE SEULE des commandes externes traitées (support/debug)."""

    queryset = CommandeSync.objects.select_related('connexion').all()
    serializer_class = CommandeSyncSerializer
    http_method_names = ['get', 'head', 'options']
