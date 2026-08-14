"""Routes publiques Stock (XPUR22 — portail fournisseur ; XPOS17 — fiche
produit showroom), sans login, montées sous /api/django/public/stock/."""
from django.urls import path
from .public_views import (
    portail_fournisseur_documents_view, portail_fournisseur_confirmer_bcf_view,
    fiche_produit_showroom_view, fiche_produit_etre_rappele_view,
    quai_checkin_view, portail_tiers_solde_view,
)

urlpatterns = [
    # NTWMS8 - kiosque de quai : le chauffeur externe s'enregistre sans compte.
    path('quai-checkin/', quai_checkin_view, name='stock-public-quai-checkin'),
    # NTWMS20 - portail 3PL (lecture seule, un seul depositaire par jeton).
    path('tiers/<str:token>/solde/', portail_tiers_solde_view,
         name='stock-public-portail-tiers-solde'),
    path('portail-fournisseur/<str:token>/',
         portail_fournisseur_documents_view,
         name='stock-public-portail-fournisseur'),
    path('portail-fournisseur/<str:token>/bcf/<int:bcf_id>/confirmer/',
         portail_fournisseur_confirmer_bcf_view,
         name='stock-public-portail-fournisseur-confirmer'),
    # XPOS17 — fiche produit publique (QR showroom, e-catalogue FG214).
    path('showroom/<str:token>/produit/<int:produit_id>/',
         fiche_produit_showroom_view,
         name='stock-public-showroom-produit'),
    path('showroom/<str:token>/produit/<int:produit_id>/etre-rappele/',
         fiche_produit_etre_rappele_view,
         name='stock-public-showroom-etre-rappele'),
]
