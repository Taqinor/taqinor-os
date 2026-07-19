from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OptionProduitViewSet, ContrainteCompatibiliteViewSet,
    RegleProduitCPQViewSet, OffreGroupeeViewSet, PrixContractuelViewSet,
    QuestionConfigurateurViewSet, ConfigurateurDemarrerView,
    ConfigurateurRepondreView, ConfigurateurResultatView,
    ConfigurateurGenererDevisView, ValiderCompatibiliteView,
    SeuilMargeFamilleViewSet, RegleApprobationRemiseViewSet,
)

router = DefaultRouter()
router.register(r'options-produit', OptionProduitViewSet)
router.register(r'contraintes-compatibilite', ContrainteCompatibiliteViewSet)
router.register(r'regles', RegleProduitCPQViewSet)
router.register(r'offres-groupees', OffreGroupeeViewSet)
router.register(r'prix-contractuels', PrixContractuelViewSet)
router.register(r'configurateur-questions', QuestionConfigurateurViewSet)
# WIR105 — CRUD Paramètres CPQ (plus de dépendance au Django admin).
router.register(r'seuils-marge', SeuilMargeFamilleViewSet)
router.register(r'regles-approbation-remise', RegleApprobationRemiseViewSet)

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
    path('configurateur/<uuid:token>/generer-devis/',
         ConfigurateurGenererDevisView.as_view(),
         name='cpq-configurateur-generer-devis'),
    path('', include(router.urls)),
]
