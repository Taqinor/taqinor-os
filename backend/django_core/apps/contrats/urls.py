from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ContratViewSet

router = DefaultRouter()
router.register(r'contrats', ContratViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
