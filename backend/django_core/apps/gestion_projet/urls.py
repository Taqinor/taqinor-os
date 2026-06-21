from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProjetChantierViewSet, ProjetViewSet

router = DefaultRouter()
router.register(r'projets', ProjetViewSet)
router.register(r'projet-chantiers', ProjetChantierViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
