from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnonceProduitViewSet, CampagneInnovationViewSet, FeedbackProduitViewSet,
    FeedbackResumeView, IdeeViewSet, InnovationSettingsView, TimelineView,
    VoteIdeeViewSet,
)

router = DefaultRouter()
router.register(r'idees', IdeeViewSet, basename='idee')
router.register(r'votes', VoteIdeeViewSet, basename='vote-idee')
router.register(r'campagnes', CampagneInnovationViewSet, basename='campagne-innovation')
# NTIDE36/39 — canal feedback produit + annonces produit (repli local).
router.register(r'feedback-produit', FeedbackProduitViewSet, basename='feedback-produit')
router.register(r'annonces-produit', AnnonceProduitViewSet, basename='annonce-produit')

urlpatterns = [
    # NTIDE7 — Paramètres → Avancé « Campagnes innovation » (singleton société).
    path('parametres/', InnovationSettingsView.as_view(),
         name='innovation-parametres'),
    # NTIDE23 — graphe « idées par jour », filtres statut/contexte.
    path('timeline/', TimelineView.as_view(), name='innovation-timeline'),
    # NTIDE38 — agrégation feedback produit par thème (admin).
    path('feedback-resume/', FeedbackResumeView.as_view(),
         name='innovation-feedback-resume'),
    path('', include(router.urls)),
]
