"""Routes publiques SAV (FG86) — sans login, montées sous /api/django/public/sav/."""
from django.urls import path
from .public_views import (
    equipement_public_signaler, ticket_public_satisfaction,
    ticket_public_status,
)

urlpatterns = [
    path('ticket/<str:token>/', ticket_public_status, name='sav-public-ticket-status'),
    # XSAV10 — enquête de satisfaction (CSAT) via le même lien client.
    path('ticket/<str:token>/satisfaction/', ticket_public_satisfaction,
         name='sav-public-ticket-satisfaction'),
    # XSAV19 — page « Signaler un problème » via QR équipement (/e/<token>).
    path('equipement/<str:token>/signaler/', equipement_public_signaler,
         name='sav-public-equipement-signaler'),
]
