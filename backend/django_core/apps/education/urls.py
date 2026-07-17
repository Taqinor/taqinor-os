from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import (
    AnneeScolaireViewSet, ClasseViewSet, EleveViewSet, FamilleViewSet,
    InscriptionViewSet, NiveauViewSet)

router = DefaultRouter()
router.register(
    r'annees-scolaires', AnneeScolaireViewSet, basename='education-annee-scolaire')
router.register(r'niveaux', NiveauViewSet, basename='education-niveau')
router.register(r'classes', ClasseViewSet, basename='education-classe')
router.register(r'familles', FamilleViewSet, basename='education-famille')
router.register(r'eleves', EleveViewSet, basename='education-eleve')
router.register(
    r'inscriptions', InscriptionViewSet, basename='education-inscription')

urlpatterns = [
    path('', include(router.urls)),
]
