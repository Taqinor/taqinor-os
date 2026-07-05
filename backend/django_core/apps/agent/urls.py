from django.urls import path

from .views import AgentActionLogView, AgentActionsView, AgentActionUndoView

urlpatterns = [
    path('actions/', AgentActionsView.as_view(), name='agent-actions'),
    # YHARD2 — journal des actions IA confirmées + annulation (admin-only).
    path('logs/', AgentActionLogView.as_view(), name='agent-action-logs'),
    path('logs/<int:pk>/annuler/', AgentActionUndoView.as_view(),
         name='agent-action-undo'),
]
