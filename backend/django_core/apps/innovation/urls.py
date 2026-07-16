from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IdeeViewSet, InnovationSettingsView, VoteIdeeViewSet

router = DefaultRouter()
router.register(r'idees', IdeeViewSet, basename='idee')
router.register(r'votes', VoteIdeeViewSet, basename='vote-idee')

urlpatterns = [
    # NTIDE7 — Paramètres → Avancé « Campagnes innovation » (singleton société).
    path('parametres/', InnovationSettingsView.as_view(),
         name='innovation-parametres'),
    path('', include(router.urls)),
]
