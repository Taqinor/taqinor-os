from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DepartementViewSet

router = DefaultRouter()
router.register(r'departements', DepartementViewSet, basename='fpa-departement')

urlpatterns = [
    path('', include(router.urls)),
]
