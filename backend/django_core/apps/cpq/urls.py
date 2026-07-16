from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OptionProduitViewSet, ContrainteCompatibiliteViewSet,
    RegleProduitCPQViewSet, OffreGroupeeViewSet, PrixContractuelViewSet,
    ValiderCompatibiliteView,
)

router = DefaultRouter()
router.register(r'options-produit', OptionProduitViewSet)
router.register(r'contraintes-compatibilite', ContrainteCompatibiliteViewSet)
router.register(r'regles', RegleProduitCPQViewSet)
router.register(r'offres-groupees', OffreGroupeeViewSet)
router.register(r'prix-contractuels', PrixContractuelViewSet)

urlpatterns = [
    path('valider-compatibilite/', ValiderCompatibiliteView.as_view(),
         name='cpq-valider-compatibilite'),
    path('', include(router.urls)),
]
