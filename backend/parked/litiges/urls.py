from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReclamationViewSet

router = DefaultRouter()
router.register(r'reclamations', ReclamationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
