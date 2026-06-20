"""Routes de l'API publique de DONNÉES (N89), montées sous /api/public/.

Distinct de `apps.ventes.public_urls` (liens PDF tokenisés sous
/api/django/public/) : ici c'est l'API REST de données par clé d'API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .public_views import (
    PublicLeadViewSet, PublicDevisViewSet,
    PublicFactureViewSet, PublicChantierViewSet,
)

router = DefaultRouter()
router.register(r'leads', PublicLeadViewSet, basename='public-lead')
router.register(r'devis', PublicDevisViewSet, basename='public-devis')
router.register(r'factures', PublicFactureViewSet, basename='public-facture')
router.register(r'chantiers', PublicChantierViewSet, basename='public-chantier')

urlpatterns = [
    path('', include(router.urls)),
]
