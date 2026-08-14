from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .public_views import carte_publique
from .views import (
    CompteFideliteViewSet, PalierFideliteViewSet, ProgrammeFideliteViewSet,
)

router = DefaultRouter()
router.register(r'programmes', ProgrammeFideliteViewSet,
                basename='fidelite-programme')
router.register(r'paliers', PalierFideliteViewSet, basename='fidelite-palier')
router.register(r'comptes', CompteFideliteViewSet, basename='fidelite-compte')

urlpatterns = [
    # NTRET11 — carte publique tokenisée (douchette caisse), AVANT le router
    # pour ne jamais matcher une route CRUD.
    path('carte/<str:token>/', carte_publique, name='fidelite-carte-publique'),
    path('', include(router.urls)),
]
