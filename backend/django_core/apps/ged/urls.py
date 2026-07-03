from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArchivageLegalViewSet, CabinetViewSet, ChampSignatureViewSet,
    CoffreViewSet, DemandeApprobationViewSet, DemandeSignatureDocumentViewSet,
    DocumentLienViewSet, DocumentTagAssignmentViewSet, DocumentTagViewSet,
    DocumentVersionViewSet, DocumentViewSet, FolderViewSet, JournalAccesViewSet,
    LegalHoldViewSet, ModeleDocumentViewSet, PartageGedViewSet,
    PolitiqueRetentionViewSet, QuotaStockageViewSet, SignataireDemandeViewSet,
    public_partage, public_signataire, public_signature,
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
router.register(r'demandes-signature', DemandeSignatureDocumentViewSet)
router.register(r'signataires-demande', SignataireDemandeViewSet)
router.register(r'champs-signature', ChampSignatureViewSet)
router.register(r'journal-acces', JournalAccesViewSet)
router.register(r'quotas-stockage', QuotaStockageViewSet)

urlpatterns = [
    # GED20 — accès PUBLIC (sans login) à un document par jeton de partage.
    # AUTHENTIFIÉ UNIQUEMENT PAR LE JETON : déclaré AVANT le routeur pour ne
    # jamais être capté par une route authentifiée (le préfixe `public/` est
    # distinct des routes du routeur). AllowAny est posé sur la vue elle-même.
    path('public/<str:token>/', public_partage, name='ged-public-partage'),
    # XGED1 — cérémonie de signature PUBLIQUE (sans login), résolue par jeton
    # uniquement. Déclarée avant le routeur pour ne jamais être captée par une
    # route authentifiée.
    path('signature/<str:token>/', public_signature, name='ged-public-signature'),
    # XGED2 — cérémonie publique d'UN destinataire du circuit multi-signataires
    # (jeton propre au signataire, distinct du jeton de la demande globale).
    path('signataire/<str:token>/', public_signataire,
         name='ged-public-signataire'),
    path('', include(router.urls)),
]
