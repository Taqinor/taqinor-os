from django.urls import path

from .views import (
    PVReceptionView, BonLivraisonView, DossierRemiseView, AttestationView,
)
from .views_contrats import (
    ActeDetailView, ActeEmettreView, ActeMarquerSigneView, ActeModeleView,
    ActePdfView, ActeRouvrirView, ActeSignerView, DossierContractuelView,
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
    # Dossier contractuel d'un chantier (contract_samples/*.json).
    path('chantiers/<int:pk>/contrats/',
         DossierContractuelView.as_view(), name='document-dossier-contractuel'),
    path('actes/<int:pk>/', ActeDetailView.as_view(), name='document-acte'),
    path('actes/<int:pk>/pdf/', ActePdfView.as_view(), name='document-acte-pdf'),
    path('actes/<int:pk>/emettre/', ActeEmettreView.as_view(),
         name='document-acte-emettre'),
    path('actes/<int:pk>/rouvrir/', ActeRouvrirView.as_view(),
         name='document-acte-rouvrir'),
    path('actes/<int:pk>/signer/', ActeSignerView.as_view(),
         name='document-acte-signer'),
    path('actes/<int:pk>/marquer-signe/', ActeMarquerSigneView.as_view(),
         name='document-acte-marquer-signe'),
    path('actes/<int:pk>/modele/', ActeModeleView.as_view(),
         name='document-acte-modele'),
]
