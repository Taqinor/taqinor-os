"""Routes publiques Stock (XPUR22 — portail fournisseur), sans login,
montées sous /api/django/public/stock/."""
from django.urls import path
from .public_views import (
    portail_fournisseur_documents_view, portail_fournisseur_confirmer_bcf_view,
    quai_checkin_view, portail_tiers_solde_view,
    portail_fournisseur_creneaux_view,
    portail_fournisseur_reserver_creneau_view,
    panneau_par_defaut_site_view,
)

urlpatterns = [
    # NTWMS8 - kiosque de quai : le chauffeur externe s'enregistre sans compte.
    path('quai-checkin/', quai_checkin_view, name='stock-public-quai-checkin'),
    # D-ACAL-169 (a) - la puissance du panneau par defaut, lue par le site
    # public (contrat panneau_par_defaut_site.json) : Wc seule, sans login.
    path('panneau-par-defaut/', panneau_par_defaut_site_view,
         name='stock-public-panneau-par-defaut'),
    # NTWMS20 - portail 3PL (lecture seule, un seul depositaire par jeton).
    path('tiers/<str:token>/solde/', portail_tiers_solde_view,
         name='stock-public-portail-tiers-solde'),
    path('portail-fournisseur/<str:token>/',
         portail_fournisseur_documents_view,
         name='stock-public-portail-fournisseur'),
    path('portail-fournisseur/<str:token>/bcf/<int:bcf_id>/confirmer/',
         portail_fournisseur_confirmer_bcf_view,
         name='stock-public-portail-fournisseur-confirmer'),
    # NTWMS35 - le fournisseur consulte les creneaux de quai libres et reserve.
    path('portail-fournisseur/<str:token>/creneaux-disponibles/',
         portail_fournisseur_creneaux_view,
         name='stock-public-portail-fournisseur-creneaux'),
    path('portail-fournisseur/<str:token>/reserver-creneau/',
         portail_fournisseur_reserver_creneau_view,
         name='stock-public-portail-fournisseur-reserver-creneau'),
]
