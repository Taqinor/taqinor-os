"""Routes du module « ai_governance » — montées sous ``/api/django/ai/``."""
from django.urls import path

from .views import (AssistantConfigView, CrInterventionView,
                    DescriptionProduitView, RapportPeriodeView, RedigerView)

urlpatterns = [
    # NTAI35 — assistant de paramétrage (guidage seul + liens profonds).
    path('assistant-config/', AssistantConfigView.as_view(),
         name='ai-assistant-config'),
    # NTAI11 — brouillon de réponse/relance par canal (jamais envoyé).
    path('rediger/', RedigerView.as_view(), name='ai-rediger'),
    # NTAI12 — mémo vocal → compte rendu d'intervention structuré (SAV).
    path('cr-intervention/', CrInterventionView.as_view(),
         name='ai-cr-intervention'),
    # NTAI13 — brouillon de description commerciale d'un produit catalogue.
    path('description-produit/', DescriptionProduitView.as_view(),
         name='ai-description-produit'),
    # NTAI36 — brouillon de rapport d'activité périodique (chiffres serveur).
    path('rapport-periode/', RapportPeriodeView.as_view(),
         name='ai-rapport-periode'),
]
