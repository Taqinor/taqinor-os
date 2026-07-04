"""Routes publiques installations — sans login, montées sous
/api/django/public/installations/."""
from django.urls import path

from .public_views import RFQConsultationPublicView

urlpatterns = [
    # XPUR21 — réponse fournisseur en ligne à une RFQ (token par fournisseur).
    path('rfq/<str:token>/', RFQConsultationPublicView.as_view(),
         name='installations-public-rfq'),
]
