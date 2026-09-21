from django.urls import path

from .public_views import (
    depot_contrepartie_public, portail_demande_contrat, portail_mes_contrats,
)

urlpatterns = [
    path('portail/<str:token>/', portail_mes_contrats,
         name='public-contrats-portail'),
    path('portail/<str:token>/<int:contrat_id>/demande/',
         portail_demande_contrat, name='public-contrats-portail-demande'),
    # NTDOC1 — dépôt de la version contrepartie par lien tokenisé.
    path('depot/<str:token>/', depot_contrepartie_public,
         name='public-contrats-depot-contrepartie'),
]
