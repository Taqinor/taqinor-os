"""Routes publiques installations — sans login, montées sous
/api/django/public/installations/."""
from django.urls import path

from .public_views import (
    InterventionLienClientPublicView, InterventionRapportPdfPublicView,
    InterventionRapportPhotoPublicView, InterventionRapportPublicView,
)

urlpatterns = [
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
    # APDF38 / ACHT68 — photos de la page publique, servies par le jeton
    # (`photo/` = URL du payload ; `photos/` = alias de l'énoncé ACHT68).
    path('intervention-rapport/<str:token>/photo/<int:att_id>/',
         InterventionRapportPhotoPublicView.as_view(),
         name='installations-public-intervention-rapport-photo'),
    path('intervention-rapport/<str:token>/photos/<int:att_id>/',
         InterventionRapportPhotoPublicView.as_view(),
         name='installations-public-intervention-rapport-photos'),
]
