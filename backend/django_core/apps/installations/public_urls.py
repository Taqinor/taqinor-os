"""Routes publiques installations — sans login, montées sous
/api/django/public/installations/."""
from django.urls import path

from .public_views import (
    InterventionLienClientPublicView, RFQConsultationPublicView,
)

urlpatterns = [
    # XPUR21 — réponse fournisseur en ligne à une RFQ (token par fournisseur).
    path('rfq/<str:token>/', RFQConsultationPublicView.as_view(),
         name='installations-public-rfq'),
    # XFSM7 — suivi public « technicien en route » d'une intervention.
    path('intervention/<str:token>/',
         InterventionLienClientPublicView.as_view(),
         name='installations-public-intervention'),
]
