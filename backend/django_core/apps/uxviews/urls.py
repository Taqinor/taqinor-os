from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FavoriUtilisateurViewSet, SavedViewViewSet

router = DefaultRouter()
router.register(r'saved-views', SavedViewViewSet, basename='savedview')
# NTUX12 — favoris épinglés par utilisateur.
router.register(r'favoris', FavoriUtilisateurViewSet, basename='favori')

urlpatterns = [
    path('', include(router.urls)),
]
