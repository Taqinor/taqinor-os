from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompteComptableViewSet, CompteTresorerieViewSet, EcritureComptableViewSet,
    EtatsComptablesViewSet, ExerciceComptableViewSet, ImmobilisationViewSet,
    JournalViewSet, PeriodeComptableViewSet, PlanComptableViewSet,
)

router = DefaultRouter()
router.register(r'plans', PlanComptableViewSet)
router.register(r'comptes', CompteComptableViewSet)
router.register(r'journaux', JournalViewSet)
router.register(r'ecritures', EcritureComptableViewSet)
router.register(r'tresorerie', CompteTresorerieViewSet)
router.register(r'periodes', PeriodeComptableViewSet)
router.register(r'exercices', ExerciceComptableViewSet)
router.register(r'immobilisations', ImmobilisationViewSet)
router.register(r'etats', EtatsComptablesViewSet, basename='etats')

urlpatterns = [
    path('', include(router.urls)),
]
