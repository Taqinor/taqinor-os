from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionCorrectivePreventiveViewSet, NonConformiteViewSet,
    PlanInspectionChantierViewSet, PlanInspectionModeleViewSet,
    PointControleModeleViewSet, ReleveControleViewSet,
)

router = DefaultRouter()
router.register(r'non-conformites', NonConformiteViewSet)
router.register(r'capa', ActionCorrectivePreventiveViewSet)
router.register(r'plans-inspection', PlanInspectionModeleViewSet)
router.register(r'points-controle', PointControleModeleViewSet)
router.register(r'plans-chantier', PlanInspectionChantierViewSet)
router.register(r'releves', ReleveControleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
