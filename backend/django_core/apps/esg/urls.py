from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CatalogueIndicateurESGViewSet, ObjectifESGTrajectoireViewSet,
    PeriodeReportingESGViewSet,
)

router = DefaultRouter()
router.register(
    r'periodes-esg', PeriodeReportingESGViewSet, basename='esg-periode')
router.register(
    r'catalogue-esg', CatalogueIndicateurESGViewSet, basename='esg-catalogue')
router.register(
    r'objectifs-esg', ObjectifESGTrajectoireViewSet, basename='esg-objectif')

urlpatterns = [
    path('', include(router.urls)),
]
