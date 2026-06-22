from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProjetChantierViewSet, ProjetLienViewSet, ProjetViewSet

router = DefaultRouter()
router.register(r'projets', ProjetViewSet)
router.register(r'projet-chantiers', ProjetChantierViewSet)
router.register(r'projet-liens', ProjetLienViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
