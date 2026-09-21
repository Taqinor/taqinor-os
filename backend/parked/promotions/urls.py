from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReglexPromotionViewSet

router = DefaultRouter()
router.register(r'regles', ReglexPromotionViewSet, basename='promotion-regle')

urlpatterns = [
    path('', include(router.urls)),
]
