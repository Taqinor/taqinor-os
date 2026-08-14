from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import webhook_commande_shopify
from .views import (
    CommandeSyncViewSet, ConnexionEcommerceViewSet, ProduitSyncViewSet,
)

router = DefaultRouter()
router.register(r'connexions', ConnexionEcommerceViewSet,
                basename='ecommerce-connexion')
router.register(r'produits-sync', ProduitSyncViewSet,
                basename='ecommerce-produit-sync')
router.register(r'commandes', CommandeSyncViewSet,
                basename='ecommerce-commande')

urlpatterns = [
    # NTRET18 — webhook Shopify PUBLIC (signature HMAC = authentification),
    # AVANT le router pour ne jamais matcher une route CRUD.
    path('shopify/webhook/commande/', webhook_commande_shopify,
         name='ecommerce-shopify-webhook-commande'),
    path('', include(router.urls)),
]
