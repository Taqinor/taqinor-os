from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CatalogueIndicateurESGViewSet, DocumentPolitiqueESGViewSet,
    FacteurEmissionReferenceViewSet, ObjectifESGTrajectoireViewSet,
    ParametresESGView, PartiePrenanteESGViewSet, PeriodeReportingESGViewSet,
)

router = DefaultRouter()
router.register(
    r'periodes-esg', PeriodeReportingESGViewSet, basename='esg-periode')
router.register(
    r'catalogue-esg', CatalogueIndicateurESGViewSet, basename='esg-catalogue')
router.register(
    r'objectifs-esg', ObjectifESGTrajectoireViewSet, basename='esg-objectif')
router.register(
    r'parties-prenantes-esg', PartiePrenanteESGViewSet,
    basename='esg-partie-prenante')
router.register(
    r'documents-politique-esg', DocumentPolitiqueESGViewSet,
    basename='esg-document-politique')
router.register(
    r'facteurs-emission', FacteurEmissionReferenceViewSet,
    basename='esg-facteur-emission')

urlpatterns = [
    # NTESG20 — déclaré AVANT le routeur (aucune collision aujourd'hui, mais
    # c'est la convention du dépôt pour une route fixe voisine d'un routeur).
    path('parametres-esg/', ParametresESGView.as_view(),
         name='esg-parametres'),
    path('', include(router.urls)),
]
