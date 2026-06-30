from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArchivageLegalViewSet, CabinetViewSet, CoffreViewSet,
    DemandeApprobationViewSet, DocumentLienViewSet,
    DocumentTagAssignmentViewSet, DocumentTagViewSet, DocumentVersionViewSet,
    DocumentViewSet, FolderViewSet, LegalHoldViewSet, ModeleDocumentViewSet,
    PartageGedViewSet, PolitiqueRetentionViewSet, public_partage,
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
router.register(r'demandes-approbation', DemandeApprobationViewSet)
router.register(r'partages', PartageGedViewSet)
router.register(r'politiques-retention', PolitiqueRetentionViewSet)
router.register(r'archivages-legaux', ArchivageLegalViewSet)
router.register(r'legal-holds', LegalHoldViewSet)
router.register(r'modeles-document', ModeleDocumentViewSet)

urlpatterns = [
    # GED20 — accès PUBLIC (sans login) à un document par jeton de partage.
    # AUTHENTIFIÉ UNIQUEMENT PAR LE JETON : déclaré AVANT le routeur pour ne
    # jamais être capté par une route authentifiée (le préfixe `public/` est
    # distinct des routes du routeur). AllowAny est posé sur la vue elle-même.
    path('public/<str:token>/', public_partage, name='ged-public-partage'),
    path('', include(router.urls)),
]
