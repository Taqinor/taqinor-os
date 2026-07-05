"""Routes publiques installations — sans login, montées sous
/api/django/public/installations/."""
from django.urls import path

from .public_views import (
    InterventionLienClientPublicView, InterventionRapportPdfPublicView,
    InterventionRapportPublicView, RFQConsultationPublicView,
)

urlpatterns = [
    # XPUR21 — réponse fournisseur en ligne à une RFQ (token par fournisseur).
    path('rfq/<str:token>/', RFQConsultationPublicView.as_view(),
         name='installations-public-rfq'),
    # XFSM7 — suivi public « technicien en route » d'une intervention.
    path('intervention/<str:token>/',
         InterventionLienClientPublicView.as_view(),
         name='installations-public-intervention'),
    # ZFSM2 — compte-rendu d'intervention signé (page + PDF), token distinct.
    path('intervention-rapport/<str:token>/',
         InterventionRapportPublicView.as_view(),
         name='installations-public-intervention-rapport'),
    path('intervention-rapport/<str:token>/pdf/',
         InterventionRapportPdfPublicView.as_view(),
         name='installations-public-intervention-rapport-pdf'),
]
