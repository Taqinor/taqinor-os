from django.urls import path

from .public_views import portail_demande_contrat, portail_mes_contrats

urlpatterns = [
    path('portail/<str:token>/', portail_mes_contrats,
         name='public-contrats-portail'),
    path('portail/<str:token>/<int:contrat_id>/demande/',
         portail_demande_contrat, name='public-contrats-portail-demande'),
]
