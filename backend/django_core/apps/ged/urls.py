from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DocumentVersionViewSet, DocumentViewSet, DossierViewSet,
)

router = DefaultRouter()
router.register(r'dossiers', DossierViewSet)
router.register(r'documents', DocumentViewSet)
router.register(r'versions', DocumentVersionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
