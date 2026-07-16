from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import PraticienViewSet

router = DefaultRouter()
router.register(r'praticiens', PraticienViewSet, basename='sante-praticien')

urlpatterns = [
    path('', include(router.urls)),
]
