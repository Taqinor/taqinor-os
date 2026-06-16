from django.urls import path

from .views import (
    PVReceptionView, BonLivraisonView, DossierRemiseView, AttestationView,
)

urlpatterns = [
    path('chantiers/<int:pk>/pv-reception/',
         PVReceptionView.as_view(), name='document-pv-reception'),
    path('chantiers/<int:pk>/bon-livraison/',
         BonLivraisonView.as_view(), name='document-bon-livraison'),
    path('chantiers/<int:pk>/dossier-remise/',
         DossierRemiseView.as_view(), name='document-dossier-remise'),
    path('chantiers/<int:pk>/attestation/',
         AttestationView.as_view(), name='document-attestation'),
]
