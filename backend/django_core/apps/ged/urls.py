from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnnotationDocumentViewSet, ArchivageLegalViewSet, CabinetViewSet,
    ChampSignatureViewSet, CoffreViewSet, DemandeApprobationViewSet,
    DemandeDispositionViewSet, DemandeDocumentViewSet,
    DemandeSignatureDocumentViewSet,
    DepotPublicViewSet, DocumentLienViewSet, DocumentTagAssignmentViewSet,
    DocumentTagViewSet, DocumentVersionViewSet, DocumentViewSet,
    ExigenceDossierViewSet, FolderViewSet, JournalAccesViewSet,
    LegalHoldViewSet, LotEnvoiViewSet, ModeleDocumentViewSet, PartageGedViewSet,
    PlanificationDocumentViewSet, PolitiqueRetentionViewSet,
    QuotaStockageViewSet, RegleAclMetadonneeViewSet,
    RegleApprobationGedViewSet, RegleDossierViewSet,
    SignataireDemandeViewSet, ValidationOcrDocumentViewSet,
    analytique_ged, public_depot, public_partage, public_signataire,
    public_signature,
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
router.register(r'depots-publics', DepotPublicViewSet)
router.register(r'exigences-dossier', ExigenceDossierViewSet)
router.register(r'demandes-document', DemandeDocumentViewSet)
router.register(r'validations-ocr', ValidationOcrDocumentViewSet)
router.register(r'annotations', AnnotationDocumentViewSet)
router.register(r'regles-dossier', RegleDossierViewSet)
router.register(r'regles-approbation', RegleApprobationGedViewSet)
router.register(r'regles-acl-metadonnee', RegleAclMetadonneeViewSet)
router.register(r'demandes-disposition', DemandeDispositionViewSet)
router.register(r'lots-envoi', LotEnvoiViewSet)
router.register(r'planifications', PlanificationDocumentViewSet)

urlpatterns = [
    # GED20 — accès PUBLIC (sans login) à un document par jeton de partage.
    # AUTHENTIFIÉ UNIQUEMENT PAR LE JETON : déclaré AVANT le routeur pour ne
    # jamais être capté par une route authentifiée (le préfixe `public/` est
    # distinct des routes du routeur). AllowAny est posé sur la vue elle-même.
    path('public/<str:token>/', public_partage, name='ged-public-partage'),
    # XGED7 — lien public de DÉPÔT (upload-request), symétrique de GED20.
    path('depot/<str:token>/', public_depot, name='ged-public-depot'),
    # XGED1 — cérémonie de signature PUBLIQUE (sans login), résolue par jeton
    # uniquement. Déclarée avant le routeur pour ne jamais être captée par une
    # route authentifiée.
    path('signature/<str:token>/', public_signature, name='ged-public-signature'),
    # XGED2 — cérémonie publique d'UN destinataire du circuit multi-signataires
    # (jeton propre au signataire, distinct du jeton de la demande globale).
    path('signataire/<str:token>/', public_signataire,
         name='ged-public-signataire'),
    # XGED26 — analytique workflow & signature (authentifié, gestion/admin).
    # Déclaré avant le routeur pour ne pas être capté par une route de detail
    # DRF (ex. un futur `<pk>/`) — même précaution que les routes publiques.
    path('analytique/', analytique_ged, name='ged-analytique'),
    path('', include(router.urls)),
]
