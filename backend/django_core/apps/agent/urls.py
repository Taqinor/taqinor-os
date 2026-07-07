from django.urls import path

from .views import (AgentActionLogView, AgentActionsView, AgentActionUndoView,
                    AutomationDraftView)

urlpatterns = [
    path('actions/', AgentActionsView.as_view(), name='agent-actions'),
    # XPLT18 — proposer une règle d'automatisation en langage naturel.
    path('actions/automation-draft/', AutomationDraftView.as_view(),
         name='agent-automation-draft'),
    # YHARD2 — journal des actions IA confirmées + annulation (admin-only).
    path('logs/', AgentActionLogView.as_view(), name='agent-action-logs'),
    path('logs/<int:pk>/annuler/', AgentActionUndoView.as_view(),
         name='agent-action-undo'),
]
