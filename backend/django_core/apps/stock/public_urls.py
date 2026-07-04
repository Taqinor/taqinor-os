"""Routes publiques Stock (XPUR22 — portail fournisseur), sans login,
montées sous /api/django/public/stock/."""
from django.urls import path
from .public_views import (
    portail_fournisseur_documents_view, portail_fournisseur_confirmer_bcf_view,
)

urlpatterns = [
    path('portail-fournisseur/<str:token>/',
         portail_fournisseur_documents_view,
         name='stock-public-portail-fournisseur'),
    path('portail-fournisseur/<str:token>/bcf/<int:bcf_id>/confirmer/',
         portail_fournisseur_confirmer_bcf_view,
         name='stock-public-portail-fournisseur-confirmer'),
]
