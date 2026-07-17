from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CampagneInnovationViewSet, IdeeViewSet, InnovationSettingsView,
    TimelineView, VoteIdeeViewSet,
)

router = DefaultRouter()
router.register(r'idees', IdeeViewSet, basename='idee')
router.register(r'votes', VoteIdeeViewSet, basename='vote-idee')
router.register(r'campagnes', CampagneInnovationViewSet, basename='campagne-innovation')

urlpatterns = [
    # NTIDE7 — Paramètres → Avancé « Campagnes innovation » (singleton société).
    path('parametres/', InnovationSettingsView.as_view(),
         name='innovation-parametres'),
    # NTIDE23 — graphe « idées par jour », filtres statut/contexte.
    path('timeline/', TimelineView.as_view(), name='innovation-timeline'),
    path('', include(router.urls)),
]
