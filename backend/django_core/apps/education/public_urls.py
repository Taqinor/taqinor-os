"""NTEDU31/32/34 — routes PUBLIQUES (sans login) du portail parents, montées
sous ``api/django/public/education/`` par ``erp_agentique.urls`` (même
patron que ``apps.contrats.public_urls``)."""
from django.urls import path

from .public_views import (
    portail_echeancier, portail_liste_attente, portail_mes_eleves,
)

urlpatterns = [
    path('portail/<str:token>/eleves/', portail_mes_eleves,
         name='public-education-portail-eleves'),
    path('portail/<str:token>/echeancier/', portail_echeancier,
         name='public-education-portail-echeancier'),
    path('portail/<str:token>/liste-attente/', portail_liste_attente,
         name='public-education-portail-liste-attente'),
]
