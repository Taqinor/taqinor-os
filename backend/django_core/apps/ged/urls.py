from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CabinetViewSet, CoffreViewSet, DocumentLienViewSet,
    DocumentTagAssignmentViewSet, DocumentTagViewSet, DocumentVersionViewSet,
    DocumentViewSet, FolderViewSet,
)

router = DefaultRouter()
router.register(r'cabinets', CabinetViewSet)
router.register(r'coffres', CoffreViewSet)
router.register(r'dossiers', FolderViewSet)
router.register(r'documents', DocumentViewSet)
router.register(r'versions', DocumentVersionViewSet)
router.register(r'liens', DocumentLienViewSet)
router.register(r'tags', DocumentTagViewSet)
router.register(r'tag-assignments', DocumentTagAssignmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
