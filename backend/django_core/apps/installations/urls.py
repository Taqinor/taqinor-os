from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InstallationViewSet, InterventionViewSet, TypeInterventionViewSet,
    ChecklistTemplateViewSet, ChecklistEtapeModeleViewSet, ShotListSlotViewSet,
)

router = DefaultRouter()
router.register(r'chantiers', InstallationViewSet)
router.register(r'interventions', InterventionViewSet)
router.register(r'types-intervention', TypeInterventionViewSet)
router.register(r'checklist-templates', ChecklistTemplateViewSet)
router.register(r'checklist-etapes', ChecklistEtapeModeleViewSet)
router.register(r'shotlist-slots', ShotListSlotViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
