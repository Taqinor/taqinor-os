"""NTEDU31/32/33/34 — routes PUBLIQUES (sans login) du portail parents,
montées sous ``api/django/public/education/`` par ``erp_agentique.urls``
(même patron que ``apps.contrats.public_urls``)."""
from django.urls import path

from .public_views import (
    portail_bulletin_pdf, portail_bulletins, portail_echeancier,
    portail_liste_attente, portail_mes_eleves, portail_presences,
)

urlpatterns = [
    path('portail/<str:token>/eleves/', portail_mes_eleves,
         name='public-education-portail-eleves'),
    path('portail/<str:token>/echeancier/', portail_echeancier,
         name='public-education-portail-echeancier'),
    path('portail/<str:token>/liste-attente/', portail_liste_attente,
         name='public-education-portail-liste-attente'),
    # NTEDU33 — historique de présence + bulletins PUBLIÉS.
    path('portail/<str:token>/presences/', portail_presences,
         name='public-education-portail-presences'),
    path('portail/<str:token>/bulletins/', portail_bulletins,
         name='public-education-portail-bulletins'),
    path('portail/<str:token>/bulletins/<int:bulletin_id>/pdf/',
         portail_bulletin_pdf,
         name='public-education-portail-bulletin-pdf'),
]
