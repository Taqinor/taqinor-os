"""Routes du module « ai_governance » — montées sous ``/api/django/ai/``."""
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (AnalyserContratView, AssistantConfigView,
                    CrInterventionView, DescriptionProduitView, ExtraireView,
                    ProchainesActionsView, RapportPeriodeView,
                    RechercheGlobaleView, RedigerView, ResumeFicheView,
                    ResumerDocumentView)
from .viewsets import DocumentAiJobViewSet

# SimpleRouter (et non DefaultRouter) : le préfixe `/api/django/ai/` ne doit
# pas gagner une vue « api-root » qu'il n'avait pas.
router = SimpleRouter()
# NTAI17/NTAI18 — file des traitements IA de documents + revue humaine.
router.register(r'documents-ai-jobs', DocumentAiJobViewSet,
                basename='document-ai-job')

urlpatterns = [
    # NTAI35 — assistant de paramétrage (guidage seul + liens profonds).
    path('assistant-config/', AssistantConfigView.as_view(),
         name='ai-assistant-config'),
    # NTAI8 — résumé FR de la situation d'une fiche (lecture seule).
    path('resume-fiche/', ResumeFicheView.as_view(), name='ai-resume-fiche'),
    # NTAI9 — 1 à 3 prochaines actions priorisées (propose, n'exécute jamais).
    path('prochaines-actions/', ProchainesActionsView.as_view(),
         name='ai-prochaines-actions'),
    # NTAI11 — brouillon de réponse/relance par canal (jamais envoyé).
    path('rediger/', RedigerView.as_view(), name='ai-rediger'),
    # NTAI12 — mémo vocal → compte rendu d'intervention structuré (SAV).
    path('cr-intervention/', CrInterventionView.as_view(),
         name='ai-cr-intervention'),
    # NTAI20 — résumé d'un long document (map-reduce), repli sur l'aperçu.
    path('resumer-document/', ResumerDocumentView.as_view(),
         name='ai-resumer-document'),
    # NTAI19 — analyse d'un contrat : échéances + proposition d'alerte de
    # préavis (n'écrit qu'après confirmation explicite).
    path('analyser-contrat/', AnalyserContratView.as_view(),
         name='ai-analyser-contrat'),
    # NTAI15/NTAI16 — extraction documentaire à la demande (bulletin de paie,
    # facture fournisseur…). N'écrit rien, ne conserve pas le fichier.
    path('extraire/', ExtraireView.as_view(), name='ai-extraire'),
    # NTAI13 — brouillon de description commerciale d'un produit catalogue.
    path('description-produit/', DescriptionProduitView.as_view(),
         name='ai-description-produit'),
    # NTAI36 — brouillon de rapport d'activité périodique (chiffres serveur).
    path('rapport-periode/', RapportPeriodeView.as_view(),
         name='ai-rapport-periode'),
    # NTAI25 — recherche sémantique GLOBALE avec citations (RAG sur les fiches).
    path('recherche-globale/', RechercheGlobaleView.as_view(),
         name='ai-recherche-globale'),
    path('', include(router.urls)),
]
