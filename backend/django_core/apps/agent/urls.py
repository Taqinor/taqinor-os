from django.urls import path

from .views import AgentActionsView

urlpatterns = [
    path('actions/', AgentActionsView.as_view(), name='agent-actions'),
]
