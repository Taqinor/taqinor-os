"""Lien public tokenisé (sans login) vers le PDF du ticket de caisse — XPOS3.

Même patron que ``apps.ventes.public_urls`` (montage séparé, hors permissions
internes)."""
from django.urls import path

from .views import PublicTicketPDFView

urlpatterns = [
    path('ticket/<str:token>/', PublicTicketPDFView.as_view(),
         name='pos-public-ticket'),
]
