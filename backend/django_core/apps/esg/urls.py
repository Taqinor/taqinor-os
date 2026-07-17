from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CatalogueIndicateurESGViewSet, DocumentPolitiqueESGViewSet,
    FacteurEmissionReferenceViewSet, ObjectifESGTrajectoireViewSet,
    PartiePrenanteESGViewSet, PeriodeReportingESGViewSet,
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
    path('', include(router.urls)),
]
