from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OutillageViewSet, KitOutillageViewSet, KitOutillageItemViewSet,
)

router = DefaultRouter()
router.register(r'outils', OutillageViewSet)
router.register(r'kits', KitOutillageViewSet)
router.register(r'kit-items', KitOutillageItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
