from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CabinetViewSet, DocumentLienViewSet, DocumentVersionViewSet,
    DocumentViewSet, FolderViewSet,
)

router = DefaultRouter()
router.register(r'cabinets', CabinetViewSet)
router.register(r'dossiers', FolderViewSet)
router.register(r'documents', DocumentViewSet)
router.register(r'versions', DocumentVersionViewSet)
router.register(r'liens', DocumentLienViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
