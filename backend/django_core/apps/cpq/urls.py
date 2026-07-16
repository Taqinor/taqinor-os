from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OptionProduitViewSet, ContrainteCompatibiliteViewSet,
    RegleProduitCPQViewSet, OffreGroupeeViewSet, PrixContractuelViewSet,
    QuestionConfigurateurViewSet, ConfigurateurDemarrerView,
    ConfigurateurRepondreView, ConfigurateurResultatView,
    ValiderCompatibiliteView,
)

router = DefaultRouter()
router.register(r'options-produit', OptionProduitViewSet)
router.register(r'contraintes-compatibilite', ContrainteCompatibiliteViewSet)
router.register(r'regles', RegleProduitCPQViewSet)
router.register(r'offres-groupees', OffreGroupeeViewSet)
router.register(r'prix-contractuels', PrixContractuelViewSet)
router.register(r'configurateur-questions', QuestionConfigurateurViewSet)

urlpatterns = [
    path('valider-compatibilite/', ValiderCompatibiliteView.as_view(),
         name='cpq-valider-compatibilite'),
    path('configurateur/demarrer/', ConfigurateurDemarrerView.as_view(),
         name='cpq-configurateur-demarrer'),
    path('configurateur/<uuid:token>/repondre/',
         ConfigurateurRepondreView.as_view(),
         name='cpq-configurateur-repondre'),
    path('configurateur/<uuid:token>/resultat/',
         ConfigurateurResultatView.as_view(),
         name='cpq-configurateur-resultat'),
    path('', include(router.urls)),
]
