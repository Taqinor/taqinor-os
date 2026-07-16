from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OptionProduitViewSet, ContrainteCompatibiliteViewSet,
    RegleProduitCPQViewSet, OffreGroupeeViewSet, ValiderCompatibiliteView,
)

router = DefaultRouter()
router.register(r'options-produit', OptionProduitViewSet)
router.register(r'contraintes-compatibilite', ContrainteCompatibiliteViewSet)
router.register(r'regles', RegleProduitCPQViewSet)
router.register(r'offres-groupees', OffreGroupeeViewSet)

urlpatterns = [
    path('valider-compatibilite/', ValiderCompatibiliteView.as_view(),
         name='cpq-valider-compatibilite'),
    path('', include(router.urls)),
]
