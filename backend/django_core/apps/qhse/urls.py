from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActionCorrectivePreventiveViewSet, NonConformiteViewSet,
)

router = DefaultRouter()
router.register(r'non-conformites', NonConformiteViewSet)
router.register(r'capa', ActionCorrectivePreventiveViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
