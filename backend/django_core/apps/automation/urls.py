from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AutomationApprovalViewSet, AutomationRuleViewSet, AutomationRunViewSet,
    automation_templates,
)

router = DefaultRouter()
router.register(r'rules', AutomationRuleViewSet)
router.register(r'runs', AutomationRunViewSet)
router.register(r'approvals', AutomationApprovalViewSet)

urlpatterns = [
    # FG3 — bibliothèque de modèles prédéfinis (lecture seule).
    path('templates/', automation_templates, name='automation-templates'),
    path('', include(router.urls)),
]
