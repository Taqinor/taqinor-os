from django.urls import path

from .public_views import incoming_webhook

urlpatterns = [
    # XPLT4 — webhook entrant générique (token dans l'URL, company résolue
    # UNIQUEMENT par le token, jamais par le payload).
    path('hooks/<str:token>/', incoming_webhook, name='automation-inbound-webhook'),
]
