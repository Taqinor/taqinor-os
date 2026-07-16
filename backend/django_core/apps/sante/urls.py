from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .viewsets import PraticienViewSet, SalleViewSet

router = DefaultRouter()
router.register(r'praticiens', PraticienViewSet, basename='sante-praticien')
router.register(r'salles', SalleViewSet, basename='sante-salle')

urlpatterns = [
    path('', include(router.urls)),
]
