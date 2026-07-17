from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CatalogueIndicateurESGViewSet, ObjectifESGTrajectoireViewSet,
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

urlpatterns = [
    path('', include(router.urls)),
]
