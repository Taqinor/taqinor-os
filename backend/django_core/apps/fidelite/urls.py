from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompteFideliteViewSet, PalierFideliteViewSet, ProgrammeFideliteViewSet,
)

router = DefaultRouter()
router.register(r'programmes', ProgrammeFideliteViewSet,
                basename='fidelite-programme')
router.register(r'paliers', PalierFideliteViewSet, basename='fidelite-palier')
router.register(r'comptes', CompteFideliteViewSet, basename='fidelite-compte')

urlpatterns = [
    path('', include(router.urls)),
]
