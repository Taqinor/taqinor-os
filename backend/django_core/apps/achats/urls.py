"""Routes du module Achats (``apps.achats``) — ODX20.

Nouveau préfixe ``/api/django/achats/…``. Les mêmes ViewSets sont AUSSI servis
par ``apps.stock.urls`` sous ``/api/django/stock/…`` (routes historiques
conservées à l'identique pour ne casser aucun client). Les ViewSets gardent le
scoping ``request.user.company`` + l'assignation forcée de ``company`` (hérité de
``TenantMixin``).

Basenames explicitement préfixés ``ach-`` pour NE PAS entrer en collision avec
les noms d'URL du routeur stock (qui reverse ``boncommandefournisseur-list`` etc.).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BonCommandeFournisseurViewSet,
    FactureFournisseurViewSet,
    PaiementFournisseurViewSet,
    PrixFournisseurViewSet,
    ReceptionFournisseurViewSet,
    RetourFournisseurViewSet,
)

router = DefaultRouter()
router.register(r'bons-commande-fournisseur', BonCommandeFournisseurViewSet,
                basename='ach-bon-commande-fournisseur')
router.register(r'receptions-fournisseur', ReceptionFournisseurViewSet,
                basename='ach-reception-fournisseur')
router.register(r'factures-fournisseur', FactureFournisseurViewSet,
                basename='ach-facture-fournisseur')
router.register(r'paiements-fournisseur', PaiementFournisseurViewSet,
                basename='ach-paiement-fournisseur')
router.register(r'retours-fournisseur', RetourFournisseurViewSet,
                basename='ach-retour-fournisseur')
router.register(r'prix-fournisseurs', PrixFournisseurViewSet,
                basename='ach-prix-fournisseur')

urlpatterns = [
    path('', include(router.urls)),
]
