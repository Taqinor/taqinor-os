from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet

router = DefaultRouter()
router.register(r'', RoleViewSet, basename='roles')

urlpatterns = [
    path('', include(router.urls)),
]
