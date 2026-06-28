from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionCorrectivePreventiveViewSet, AuditViewSet, CritereAuditViewSet,
    GrilleAuditViewSet, NonConformiteViewSet,
    PlanInspectionChantierViewSet, PlanInspectionModeleViewSet,
    PointControleModeleViewSet, QhseChatterEntryViewSet,
    ReleveControleViewSet, ReleveCourbeIVViewSet, ReponseCritereViewSet,
)

router = DefaultRouter()
router.register(r'non-conformites', NonConformiteViewSet)
router.register(r'capa', ActionCorrectivePreventiveViewSet)
router.register(r'plans-inspection', PlanInspectionModeleViewSet)
router.register(r'points-controle', PointControleModeleViewSet)
router.register(r'plans-chantier', PlanInspectionChantierViewSet)
router.register(r'releves', ReleveControleViewSet)
router.register(r'courbes-iv', ReleveCourbeIVViewSet)
router.register(r'chatter', QhseChatterEntryViewSet)
router.register(r'grilles-audit', GrilleAuditViewSet)
router.register(r'criteres-audit', CritereAuditViewSet)
router.register(r'audits', AuditViewSet)
router.register(r'reponses-critere', ReponseCritereViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
