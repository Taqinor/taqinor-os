from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TerritoireMembreViewSet, TerritoireRegleViewSet, TerritoireViewSet

router = DefaultRouter()
router.register(r'territoires', TerritoireViewSet)
router.register(r'regles', TerritoireRegleViewSet)
router.register(r'membres', TerritoireMembreViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
