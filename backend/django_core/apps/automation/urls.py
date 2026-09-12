from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalDelegationViewSet, ApprovalRequestTypeViewSet,
    ApprovalRequestViewSet, AutomationApprovalViewSet, AutomationRuleViewSet,
    AutomationRuleVersionViewSet, AutomationRunViewSet,
    IncomingWebhookTriggerViewSet, automation_templates,
)

router = DefaultRouter()
router.register(r'rules', AutomationRuleViewSet)
# NTEXT30 — historique des versions d'une règle (?rule=<id>) + restauration.
router.register(r'rule-versions', AutomationRuleVersionViewSet,
                basename='automation-rule-version')
router.register(r'runs', AutomationRunViewSet)
router.register(r'approvals', AutomationApprovalViewSet)
router.register(r'approval-request-types', ApprovalRequestTypeViewSet)
router.register(r'approval-requests', ApprovalRequestViewSet)
router.register(r'approval-delegations', ApprovalDelegationViewSet)
router.register(r'incoming-webhooks', IncomingWebhookTriggerViewSet)

urlpatterns = [
    # FG3 — bibliothèque de modèles prédéfinis (lecture seule).
    path('templates/', automation_templates, name='automation-templates'),
    path('', include(router.urls)),
]
