from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FavoriUtilisateurViewSet, SavedViewViewSet, UxParametresView

router = DefaultRouter()
router.register(r'saved-views', SavedViewViewSet, basename='savedview')
# NTUX12 — favoris épinglés par utilisateur.
router.register(r'favoris', FavoriUtilisateurViewSet, basename='favori')

urlpatterns = [
    # NTUX27 — réglages UX de la société (singleton, écran /parametres/ux).
    path('parametres/', UxParametresView.as_view(), name='ux-parametres'),
    path('', include(router.urls)),
]
