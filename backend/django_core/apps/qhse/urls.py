from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionCorrectivePreventiveViewSet, NonConformiteViewSet,
    PlanInspectionChantierViewSet, PlanInspectionModeleViewSet,
    PointControleModeleViewSet, ReleveControleViewSet,
    ReleveCourbeIVViewSet,
)

router = DefaultRouter()
router.register(r'non-conformites', NonConformiteViewSet)
router.register(r'capa', ActionCorrectivePreventiveViewSet)
router.register(r'plans-inspection', PlanInspectionModeleViewSet)
router.register(r'points-controle', PointControleModeleViewSet)
router.register(r'plans-chantier', PlanInspectionChantierViewSet)
router.register(r'releves', ReleveControleViewSet)
router.register(r'courbes-iv', ReleveCourbeIVViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
