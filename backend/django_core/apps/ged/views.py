"""API REST de la GED — tout scopé société côté serveur.

Lecture : tout rôle authentifié. Écriture : responsable/admin. La société est
TOUJOURS posée côté serveur (TenantMixin) — jamais lue du corps de requête.
Les dossiers (Folder) ont un chemin matérialisé recalculé côté serveur, et les
versions de document sont numérotées + déduppées via `services`.
"""
from django.db import models
from django.http import HttpResponse
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import (
    action, api_view, parser_classes, permission_classes, throttle_classes,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

# `records.storage` est la fondation de stockage MinIO partagée (avatars,
# pièces jointes…). On la RÉUTILISE pour l'upload GED — on ne réimplémente
# jamais le stockage objet ni un second pipeline d'upload.
# GED14 — `fetch_attachment` sert au proxy aperçu même-origine (PDF/image/texte).
from apps.records.storage import fetch_attachment, store_attachment

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
# `records` est une app de fondation : son registre de cibles autorisées
# (ALLOWED_TARGETS) et son validateur `resolve_target` sont réutilisés tels quels
# pour la liaison polymorphe GED6 — on n'invente pas un schéma de FK générique.
from apps.records.serializers import resolve_target

from . import selectors, services
from .models import (
    AnnotationDocument, ArchivageLegal, ArchivageLegalError, Cabinet,
    ChampSignature, Coffre, DemandeApprobation, DemandeDisposition,
    DemandeDispositionError, DemandeDocument,
    DemandeSignatureDocument, DepotPublic, Document, DocumentLien,
    DocumentTag, DocumentTagAssignment, DocumentVersion, ExigenceDossier,
    FavoriGed, Folder, JournalAcces, LegalHold, LegalHoldError, LotEnvoi,
    ModeleDocument,
    PartageGed, PlanificationDocument, PolitiqueRetention,
    QuotaDepasseError, QuotaStockage, RegleAclMetadonnee,
    RegleApprobationGed, RegleDossier, RoleSignataire, RoutageDocumentaire,
    SignataireDemande, TypeChampSignature, ValidationOcrDocument,
    VueGedEnregistree,
)
from .serializers import (
    AnnotationDocumentSerializer, ArchivageLegalSerializer, CabinetSerializer,
    ChampSignatureSerializer, CoffreSerializer, DemandeApprobationSerializer,
    DemandeDispositionSerializer, DemandeDocumentSerializer,
    DemandeSignatureDocumentSerializer,
    DepotPublicSerializer, DocumentLienSerializer, DocumentSerializer,
    DocumentTagAssignmentSerializer, DocumentTagSerializer,
    DocumentVersionSerializer, ExigenceDossierSerializer, FolderSerializer,
    JournalAccesSerializer, LegalHoldSerializer, LotEnvoiSerializer,
    ModeleDocumentSerializer,
    PartageGedSerializer, PlanificationDocumentSerializer,
    PolitiqueRetentionSerializer, QuotaStockageSerializer,
    RegleAclMetadonneeSerializer, RegleApprobationGedSerializer,
    RegleDossierSerializer, RoleSignataireSerializer,
    RoutageDocumentaireSerializer, SignataireDemandeSerializer,
    TypeChampSignatureSerializer, ValidationOcrDocumentSerializer,
    VueGedEnregistreeSerializer,
)

READ_ACTIONS = ['list', 'retrieve']

# GED20 — Formats affichables inline (PDF, images, texte). Tout le reste →
# téléchargement forcé (attachment). Partagé entre l'aperçu authentifié (GED14)
# et le partage public tokenisé (GED20).
_INLINE_MIMES = {
    'application/pdf',
    'image/png', 'image/jpeg', 'image/webp', 'image/gif',
    'text/plain', 'text/csv', 'text/html',
}


class _CsvOrJSONRenderer(JSONRenderer):
    """XGED22 — DRF fait la négociation de contenu sur `?format=` AVANT que
    le corps de la vue ne s'exécute (`DefaultContentNegotiation`, indépendant
    des `format_suffix_patterns`) : sans renderer déclaré pour `csv`, l'appel
    `?format=csv` échoue en amont (jamais notre `HttpResponse` renvoyée). On
    déclare donc explicitement ce format sur l'action pour que la
    négociation aboutisse ; la vue renvoie ensuite un `HttpResponse` CSV
    manuel (jamais sérialisé par ce renderer — le JSON reste le
    comportement par défaut sans `?format=csv`)."""
    format = 'csv'
    media_type = 'text/csv'


def _permissions_effectives_csv(lignes, filename_suffix):
    """XGED22 — Sérialise le rapport de permissions effectives en CSV
    (utilisateur/rôle, niveau, source de justification) pour l'export
    d'audit."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['type', 'principal', 'niveau', 'source'])
    for ligne in lignes:
        writer.writerow([
            ligne['type'], ligne['label'],
            ligne['niveau'] or '', ligne['source'],
        ])
    response = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="permissions-{filename_suffix}.csv"')
    return response


class CabinetViewSet(TenantMixin, viewsets.ModelViewSet):
    """Cabinets (armoires racines) d'une société."""
    queryset = Cabinet.objects.all()
    serializer_class = CabinetSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]


class FolderViewSet(TenantMixin, viewsets.ModelViewSet):
    """Dossiers arborescents (chemin matérialisé). Filtrable par cabinet et
    parent ; expose le sous-arbre via l'action `descendants`."""
    queryset = Folder.objects.select_related('cabinet', 'parent').all()
    serializer_class = FolderSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom']
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action in (
                'descendants', 'favori'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def _resolve_company_folder(self, folder_id):
        """Résout un dossier de la société courante, ou None.

        Borne au queryset company-scopé (TenantMixin) : un id appartenant à
        une autre société renvoie None (jamais de fuite cross-société)."""
        if folder_id in (None, '', 'null'):
            return None
        return (Folder.objects.filter(company=self.request.user.company)
                .filter(pk=folder_id).first())

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        cabinet = params.get('cabinet')
        if cabinet:
            qs = qs.filter(cabinet_id=cabinet)
        parent = params.get('parent')
        if parent == 'null':
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)
        return qs

    def perform_create(self, serializer):
        # company posée côté serveur (jamais du corps).
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'], url_path='descendants')
    def descendants(self, request, pk=None):
        """Sous-arbre strict du dossier (via le chemin matérialisé)."""
        folder = self.get_object()
        qs = folder.descendants()
        data = FolderSerializer(qs, many=True, context={'request': request}).data
        return Response(data)

    @action(detail=True, methods=['post'], url_path='deplacer')
    def deplacer(self, request, pk=None):
        """Déplace ce dossier sous un nouveau parent (déplacement scopé société).

        Body : `{"parent": <id|null>}`. Le dossier source est company-scopé via
        `get_object()` (404 cross-société). Le parent cible est résolu DANS la
        société courante — un id d'une autre société est introuvable (404). Le
        recalcul du chemin matérialisé de tout le sous-arbre est délégué à
        `services.move_folder` (refus de cycle / cabinet différent → 400)."""
        folder = self.get_object()
        raw_parent = request.data.get('parent', None)
        new_parent = None
        if raw_parent not in (None, '', 'null'):
            new_parent = self._resolve_company_folder(raw_parent)
            if new_parent is None:
                return Response(
                    {'parent': 'Dossier parent inconnu.'},
                    status=status.HTTP_404_NOT_FOUND)
        try:
            services.move_folder(folder, new_parent)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        folder.refresh_from_db()
        data = FolderSerializer(folder, context={'request': request}).data
        return Response(data)

    @action(detail=True, methods=['get'], url_path='permissions-effectives',
            renderer_classes=[JSONRenderer, BrowsableAPIRenderer, _CsvOrJSONRenderer])
    def permissions_effectives(self, request, pk=None):
        """XGED22 — Rapport de permissions effectives sur ce DOSSIER.

        `GET dossiers/<id>/permissions-effectives/` — pour chaque
        utilisateur de la société, le niveau résolu par `acl_effective` avec
        sa justification (override / héritage / règle métadonnée / admin).
        `?format=csv` exporte le même rapport en CSV. Gestion/admin
        uniquement (403 sinon)."""
        folder = self.get_object()
        lignes = selectors.permissions_effectives(folder)
        if request.query_params.get('format') == 'csv':
            return _permissions_effectives_csv(lignes, f'dossier-{folder.pk}')
        return Response({'lignes': lignes})

    @action(detail=True, methods=['post'], url_path='favori')
    def favori(self, request, pk=None):
        """ZGED7 — Bascule (toggle) ce dossier en favori pour l'appelant.

        Personnel : jamais partagé, jamais visible d'un collègue. Renvoie
        `{"favori": true|false}` selon l'état APRÈS bascule."""
        folder = self.get_object()
        deleted, _ = FavoriGed.objects.filter(
            company=request.user.company, utilisateur=request.user,
            folder=folder).delete()
        if deleted:
            return Response({'favori': False})
        FavoriGed.objects.create(
            company=request.user.company, utilisateur=request.user,
            folder=folder)
        return Response({'favori': True})


class CoffreViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED8 — Coffres-forts par employé/client (ACL propriétaire + admin).

    Liste/lecture : un employé ne voit QUE ses coffres, un admin voit tous ceux
    de sa société (filtrage `selectors.coffres_for_user`). Écriture (création/
    modification/suppression) : responsable/admin. `company` et `created_by`
    posés côté serveur ; le propriétaire est un employé OU un client (jamais les
    deux). Action `documents` : les documents du coffre (ACL appliquée).
    """
    queryset = Coffre.objects.select_related(
        'proprietaire', 'client', 'created_by').all()
    serializer_class = CoffreSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'documents':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        # ACL : remplace le filtrage company brut par le filtrage propriétaire.
        return (selectors.coffres_for_user(self.request.user)
                .select_related('proprietaire', 'client', 'created_by'))

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['get'], url_path='documents')
    def documents(self, request, pk=None):
        """Documents rattachés à ce coffre (l'accès au coffre est déjà filtré
        par `get_queryset` — un non-propriétaire reçoit un 404 sur le coffre)."""
        coffre = self.get_object()
        qs = selectors.documents_in_coffre(coffre)
        data = DocumentSerializer(
            qs, many=True, context={'request': request}).data
        return Response(data)


class DocumentViewSet(TenantMixin, viewsets.ModelViewSet):
    """Documents logiques (conteneurs versionnés) d'une société.

    GED8 — l'ACL coffre-fort est appliquée en lecture : un document placé dans
    un coffre n'est visible que de son propriétaire et des admins.
    """
    queryset = Document.objects.select_related(
        'folder', 'coffre', 'created_by').all()
    serializer_class = DocumentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    # ZGED15 — la référence lisible est cherchable/triable au même titre que
    # le nom.
    search_fields = ['nom', 'description', 'reference']
    ordering_fields = ['nom', 'reference', 'created_at', 'updated_at']

    def get_permissions(self):
        # `recherche`/`semantique`/`historique`/`check_out`/`check_in` lisibles
        # par tout rôle authentifié ; écriture réservée aux responsables/admins.
        if self.action in READ_ACTIONS or self.action in (
                'recherche', 'semantique', 'historique', 'demandes',
                'corbeille', 'comparer', 'timeline'):
            return [IsAnyRole()]
        # check_out/check_in : tout rôle peut extraire/libérer ses propres docs.
        if self.action in ('check_out', 'check_in'):
            return [IsAnyRole()]
        # ZGED7 — favoriser/défavoriser est personnel, ouvert à tout rôle.
        if self.action == 'favori':
            return [IsAnyRole()]
        # ZGED9 — verrouiller/déverrouiller (avertissement léger) : tout rôle
        # peut poser/lever SON PROPRE verrou ; la garde gestionnaire pour le
        # forçage est appliquée dans `services.deverrouiller_avertissement`.
        if self.action in ('verrouiller', 'deverrouiller'):
            return [IsAnyRole()]
        # XGED14 — le téléchargement ZIP est une lecture (lisible par tout rôle) ;
        # les autres opérations de lot restent réservées aux responsables/admins.
        if (self.action == 'operations_lot'
                and self.request.data.get('operation') == 'telecharger_zip'):
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        # GED8 — base : documents visibles selon l'ACL coffre-fort.
        qs = (selectors.documents_visible_to_user(self.request.user)
              .select_related('folder', 'coffre', 'created_by'))
        folder = self.request.query_params.get('folder')
        if folder:
            qs = qs.filter(folder_id=folder)
        coffre = self.request.query_params.get('coffre')
        if coffre == 'null':
            qs = qs.filter(coffre__isnull=True)
        elif coffre:
            qs = qs.filter(coffre_id=coffre)
        # GED9 — filtre par tag de la taxonomie (?tag=<id>).
        tag = self.request.query_params.get('tag')
        if tag:
            qs = qs.filter(tag_assignments__tag_id=tag).distinct()
        # GED17 — filtre par statut du cycle de vie documentaire (?statut=…).
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        # ZGED5 — filtres par propriétaire/contact assigné.
        proprietaire = self.request.query_params.get('proprietaire')
        if proprietaire:
            qs = qs.filter(proprietaire_id=proprietaire)
        contact = self.request.query_params.get('contact')
        if contact:
            qs = qs.filter(contact_id=contact)
        return qs

    @action(detail=True, methods=['post'], url_path='tagger')
    def tagger(self, request, pk=None):
        """GED9 — Applique un tag de la taxonomie à ce document (idempotent).

        Body : `{"tag": <id>}`. Le document est company-scopé (et ACL coffre)
        via `get_object()` ; le tag est résolu DANS la société courante."""
        document = self.get_object()
        tag_id = request.data.get('tag')
        if not tag_id:
            return Response({'tag': 'Tag requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        tag = DocumentTag.objects.filter(
            company=request.user.company, pk=tag_id).first()
        if tag is None:
            return Response({'tag': 'Tag inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        _assign, created = services.assign_tag(
            document, tag, created_by=request.user)
        return Response(
            DocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='detagger')
    def detagger(self, request, pk=None):
        """GED9 — Retire un tag de ce document. Body : `{"tag": <id>}`."""
        document = self.get_object()
        tag_id = request.data.get('tag')
        DocumentTagAssignment.objects.filter(
            company=request.user.company, document=document, tag_id=tag_id
        ).delete()
        return Response(
            DocumentSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='assigner')
    def assigner(self, request, pk=None):
        """ZGED5 — Réassigne propriétaire et/ou contact métier (panneau
        d'informations). Body optionnel : `{"proprietaire": <user_id>|null,
        "contact": <client_id>|null}` — un champ absent du body reste
        inchangé ; `null` explicite l'efface. `proprietaire` doit être un
        utilisateur de la MÊME société (404 sinon) ; `contact` est résolu via
        `apps.crm.selectors` (dégrade proprement si absent/autre société —
        aucun import du modèle crm)."""
        document = self.get_object()
        data = request.data
        if 'proprietaire' in data:
            proprietaire_id = data.get('proprietaire')
            if proprietaire_id in (None, '', 'null'):
                document.proprietaire = None
            else:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.filter(
                    pk=proprietaire_id, company=request.user.company).first()
                if user is None:
                    return Response(
                        {'proprietaire': 'Utilisateur inconnu.'},
                        status=status.HTTP_404_NOT_FOUND)
                document.proprietaire = user
        if 'contact' in data:
            contact_id = data.get('contact')
            if contact_id in (None, '', 'null'):
                document.contact_id = None
            else:
                from apps.crm.selectors import get_company_client
                client = get_company_client(request.user.company, contact_id)
                if client is None:
                    return Response(
                        {'contact': 'Client inconnu.'},
                        status=status.HTTP_404_NOT_FOUND)
                document.contact_id = client.pk
        document.save(update_fields=['proprietaire', 'contact_id', 'updated_at'])
        return Response(
            DocumentSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='favori')
    def favori(self, request, pk=None):
        """ZGED7 — Bascule (toggle) ce document en favori pour l'appelant.

        Personnel : jamais partagé, jamais visible d'un collègue. Renvoie
        `{"favori": true|false}` selon l'état APRÈS bascule."""
        document = self.get_object()
        deleted, _ = FavoriGed.objects.filter(
            company=request.user.company, utilisateur=request.user,
            document=document).delete()
        if deleted:
            return Response({'favori': False})
        FavoriGed.objects.create(
            company=request.user.company, utilisateur=request.user,
            document=document)
        return Response({'favori': True})

    def perform_create(self, serializer):
        # company + created_by posés côté serveur.
        document = serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        # GED11 — alimente le tsvector plein-texte à la création.
        services.update_search_vector(document)
        # GED12 — (ré)indexe l'embedding sémantique (no-op sans clé).
        services.index_embedding(document)
        # FG352 — (ré)indexe les fragments RAG/DocQA (no-op sans clé).
        services.index_document_chunks(document)

    def perform_update(self, serializer):
        # GED23 — write-once : un document archivé légalement est immuable (403).
        instance = getattr(serializer, 'instance', None)
        if instance is not None and instance.est_archive_legalement:
            from rest_framework.exceptions import PermissionDenied
            from .models import ARCHIVE_LEGALE_MESSAGE
            raise PermissionDenied(ARCHIVE_LEGALE_MESSAGE)
        document = serializer.save()
        # GED11 — réindexe après modification (nom/description/métadonnées).
        services.update_search_vector(document)
        # GED12 — réindexe l'embedding sémantique (no-op sans clé).
        services.index_embedding(document)
        # FG352 — réindexe les fragments RAG/DocQA (no-op sans clé).
        services.index_document_chunks(document)

    def perform_destroy(self, instance):
        # GED26 — DELETE = mise en CORBEILLE (soft-delete réversible) par défaut,
        # PAS un effacement réel. Les gardes légales restent intactes : un
        # document archivé légalement (GED23, write-once) ou sous legal hold
        # actif (GED24) N'EST PAS mettable en corbeille → 403 (jamais 500). On
        # mappe les erreurs typées levées par le service sur 403.
        from rest_framework.exceptions import PermissionDenied
        try:
            services.mettre_en_corbeille(instance, self.request.user)
        except (ArchivageLegalError, LegalHoldError) as exc:
            raise PermissionDenied(str(exc))

    @action(detail=False, methods=['post'], url_path='televerser',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def televerser(self, request):
        """Téléverse un fichier et crée le document + sa version 1 en UN appel.

        `POST …/documents/televerser/` (multipart) — corps :
        `{folder: <id>, nom?: <str>, description?: <str>, file: <binaire>}`.
        Le fichier est stocké via `records.storage.store_attachment` (même
        pipeline MinIO que les pièces jointes — on ne réimplémente pas le
        stockage), puis on crée le `Document` (company + created_by posés côté
        serveur, jamais lus du corps) et sa première `DocumentVersion`
        (numéro + uploaded_by posés côté serveur via `services.add_version`).
        Le dossier cible est borné à la société courante (404/400 sinon)."""
        company = request.user.company
        # 1) dossier cible : borné à la société (jamais un dossier d'autrui).
        folder_id = request.data.get('folder')
        if not folder_id:
            return Response({'folder': 'Le dossier cible est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        folder = (Folder.objects.filter(company=company)
                  .filter(pk=folder_id).first())
        if folder is None:
            return Response({'folder': 'Dossier inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        # 2) fichier : obligatoire, validé + stocké par records.storage.
        file = request.FILES.get('file')
        if not file:
            return Response({'file': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # GED36 — garde de quota AVANT le stockage (403, jamais 500). Un quota
        # illimité (0) ne bloque jamais.
        try:
            services.assert_quota_disponible(
                company, octets_supplementaires=getattr(file, 'size', 0))
        except QuotaDepasseError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_403_FORBIDDEN)
        meta, err = store_attachment(file)
        if err:
            return Response({'file': err},
                            status=status.HTTP_400_BAD_REQUEST)
        # 3) document : nom = saisi ou nom de fichier ; company/créateur serveur.
        nom = (request.data.get('nom') or meta['filename'] or 'Document').strip()
        document = Document.objects.create(
            company=company, folder=folder, nom=nom,
            description=(request.data.get('description') or '').strip(),
            created_by=request.user)
        # GED16 — vérifie que le document n'est pas extrait par un autre
        # utilisateur avant d'ajouter la version (televerser crée doc+v1 en
        # même temps, donc le document n'est jamais verrouillé ici — garde
        # conservatrice incluse pour les cas edge de re-creation).
        try:
            services.assert_not_locked_by_other(document, request.user)
        except PermissionError as exc:
            document.delete()
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        # 4) version 1 (numéro + uploaded_by + company posés côté serveur).
        services.add_version(
            document, file_key=meta['file_key'], company=company,
            filename=meta['filename'], size=meta['size'], mime=meta['mime'],
            uploaded_by=request.user)
        # GED11/GED12 — indexe le document fraîchement créé.
        services.update_search_vector(document)
        services.index_embedding(document)
        # FG352 — indexe les fragments RAG/DocQA (no-op sans clé).
        services.index_document_chunks(document)
        # XGED8 — un dépôt peut solder une demande de document en attente sur
        # ce dossier (best-effort, jamais bloquant).
        try:
            services.matcher_depot_demandes(document)
        except Exception:  # pragma: no cover - défensif.
            pass
        # XGED19 — règles automatiques du dossier (best-effort, ne bloque
        # jamais l'upload lui-même même si une action échoue).
        try:
            services.appliquer_regles_dossier(document, user=request.user)
        except Exception:  # pragma: no cover - défensif.
            pass
        return Response(
            DocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='scan-lot',
            parser_classes=[MultiPartParser, FormParser])
    def scan_lot(self, request):
        """GED31 — Numérisation par LOT (scan-to-DMS) : N fichiers en un appel.

        `POST …/documents/scan-lot/` (multipart) — corps :
        `{folder: <id>, files: <binaire>[, files: <binaire> …]}`. Chaque fichier
        est validé + stocké via `records.storage.store_attachment` (même pipeline
        MinIO), puis déposé comme Document + version 1 via
        `services.deposer_lot_scans` (OCR no-op sans clé + indexation). La société
        et le créateur sont posés CÔTÉ SERVEUR (jamais lus du corps). Le dossier
        cible est borné à la société (404 sinon). Écriture : responsable/admin.

        Renvoie `{documents: [...], erreurs: [...]}` — un fichier au format refusé
        est listé dans `erreurs` sans bloquer le reste du lot."""
        company = request.user.company
        folder_id = request.data.get('folder')
        if not folder_id:
            return Response({'folder': 'Le dossier cible est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        folder = (Folder.objects.filter(company=company)
                  .filter(pk=folder_id).first())
        if folder is None:
            return Response({'folder': 'Dossier inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        files = request.FILES.getlist('files') or request.FILES.getlist('file')
        if not files:
            return Response({'files': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # GED36 — garde de quota sur le LOT entier (somme des tailles), avant
        # tout stockage (403, jamais 500). Quota illimité (0) ne bloque jamais.
        total_octets = sum(getattr(f, 'size', 0) or 0 for f in files)
        try:
            services.assert_quota_disponible(
                company, octets_supplementaires=total_octets)
        except QuotaDepasseError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_403_FORBIDDEN)
        a_deposer = []
        erreurs = []
        for f in files:
            meta, err = store_attachment(f)
            if err:
                erreurs.append({'filename': getattr(f, 'name', ''),
                                'detail': err})
                continue
            a_deposer.append({
                'file_key': meta['file_key'], 'filename': meta['filename'],
                'size': meta['size'], 'mime': meta['mime'],
            })
        documents = services.deposer_lot_scans(
            company=company, folder=folder, fichiers=a_deposer,
            created_by=request.user)
        ser = DocumentSerializer(
            documents, many=True, context={'request': request})
        http = (status.HTTP_201_CREATED if documents
                else status.HTTP_400_BAD_REQUEST)
        return Response({'documents': ser.data, 'erreurs': erreurs}, status=http)

    @action(detail=False, methods=['post'], url_path='assembler-photos',
            parser_classes=[MultiPartParser, FormParser])
    def assembler_photos(self, request):
        """XGED12 — Capture mobile photo → PDF multi-pages classé en GED.

        `POST …/documents/assembler-photos/` (multipart) — corps :
        `{folder: <id>, photos: <binaire>[, photos: <binaire> …], nom?,
        description?}`. Les photos (déjà recadrées/pivotées CÔTÉ CLIENT via
        canvas — écran « Numériser » du frontend) sont assemblées en UN SEUL
        PDF multi-pages CÔTÉ SERVEUR via Pillow (déjà pinné,
        `services.assembler_photos_pdf`), puis déposées via le MÊME chemin que
        `televerser` (`services.deposer_photos_assemblees` réutilise
        `records.storage.store_attachment` + `create_document`/`add_version` —
        aucun second pipeline d'upload). L'OCR (GED33, no-op sans clé) et
        l'indexation s'appliquent au PDF assemblé comme pour tout autre dépôt.

        Le dossier cible est borné à la société courante (404 sinon). Société
        et créateur posés CÔTÉ SERVEUR (jamais lus du corps). Écriture :
        responsable/admin."""
        company = request.user.company
        folder_id = request.data.get('folder')
        if not folder_id:
            return Response({'folder': 'Le dossier cible est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        folder = (Folder.objects.filter(company=company)
                  .filter(pk=folder_id).first())
        if folder is None:
            return Response({'folder': 'Dossier inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        photos = request.FILES.getlist('photos') or request.FILES.getlist('photo')
        if not photos:
            return Response({'photos': 'Au moins une photo est requise.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # GED36 — garde de quota AVANT l'assemblage/stockage (403, jamais 500).
        total_octets = sum(getattr(p, 'size', 0) or 0 for p in photos)
        try:
            services.assert_quota_disponible(
                company, octets_supplementaires=total_octets)
        except QuotaDepasseError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_403_FORBIDDEN)
        images_bytes = [p.read() for p in photos]
        try:
            document = services.deposer_photos_assemblees(
                company=company, folder=folder, images_bytes=images_bytes,
                nom=(request.data.get('nom') or '').strip(),
                description=(request.data.get('description') or '').strip(),
                created_by=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='import-masse',
            parser_classes=[MultiPartParser, FormParser])
    def import_masse(self, request):
        """GED32 — Import en MASSE depuis un CSV de métadonnées (+ ZIP optionnel).

        `POST …/documents/import-masse/` (multipart) — corps :
        `{folder: <id>, csv: <fichier .csv>[, zip: <fichier .zip>]}`. Le CSV
        décrit une ligne par document (colonnes `nom`, `description`, `fichier`,
        + codes de champs personnalisés). Le ZIP optionnel fournit les binaires
        (appariés par la colonne `fichier`). Société + créateur posés CÔTÉ
        SERVEUR ; les champs personnalisés sont validés bornés société/module.
        Le dossier cible est borné à la société (404 sinon). Écriture :
        responsable/admin.

        Renvoie `{crees, documents: [...], erreurs: [...]}` — une ligne en erreur
        n'interrompt pas l'import."""
        company = request.user.company
        folder_id = request.data.get('folder')
        if not folder_id:
            return Response({'folder': 'Le dossier cible est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        folder = (Folder.objects.filter(company=company)
                  .filter(pk=folder_id).first())
        if folder is None:
            return Response({'folder': 'Dossier inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        csv_file = request.FILES.get('csv')
        if not csv_file:
            return Response({'csv': 'Un fichier CSV de métadonnées est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            csv_text = csv_file.read().decode('utf-8-sig')
        except (UnicodeDecodeError, AttributeError):
            return Response({'csv': 'CSV illisible (encodage attendu : UTF-8).'},
                            status=status.HTTP_400_BAD_REQUEST)
        lignes = services.parser_csv_metadonnees(csv_text)
        if not lignes:
            return Response({'csv': 'CSV vide ou sans ligne de données.'},
                            status=status.HTTP_400_BAD_REQUEST)
        zip_file = request.FILES.get('zip')
        zip_bytes = zip_file.read() if zip_file else None

        def _valider_custom(data):
            from apps.customfields.serializers import validate_custom_data
            return validate_custom_data('document', company, data)

        result = services.importer_en_masse(
            company=company, folder=folder, lignes=lignes,
            zip_bytes=zip_bytes, created_by=request.user,
            valider_custom=_valider_custom)
        ser = DocumentSerializer(
            result['documents'], many=True, context={'request': request})
        http = (status.HTTP_201_CREATED if result['crees']
                else status.HTTP_400_BAD_REQUEST)
        return Response(
            {'crees': result['crees'], 'documents': ser.data,
             'erreurs': result['erreurs']}, status=http)

    @action(detail=False, methods=['post'], url_path='classer-apres-vente')
    def classer_apres_vente(self, request):
        """GED29 — Classe un PDF APRÈS-VENTE (SAV) déjà généré dans la GED.

        `POST …/documents/classer-apres-vente/` — corps JSON :
        `{nom, source_type, source_id, file_key?, cabinet?, dossier?,
        description?}`. Le PDF référencé par `file_key` (déjà stocké en MinIO)
        est déposé et classé dans le cabinet/dossier « Après-vente » dédié
        (auto-créés si absents). La société et le créateur sont posés CÔTÉ
        SERVEUR (jamais lus du corps). Idempotent par (`source_type`,
        `source_id`) : un appel répété pour le MÊME objet SAV source renvoie le
        document déjà déposé (200) au lieu d'en dupliquer un (201).

        Point d'entrée de réception : le câblage SAV (appel à l'émission d'un
        document après-vente) est une tâche FUTURE distincte."""
        nom = (request.data.get('nom') or '').strip()
        source_type = (request.data.get('source_type') or '').strip()
        source_id = request.data.get('source_id')
        if not nom:
            return Response({'nom': 'Le nom du document est requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not source_type or source_id in (None, ''):
            return Response(
                {'detail': 'source_type et source_id sont requis '
                           '(idempotence par objet SAV source).'},
                status=status.HTTP_400_BAD_REQUEST)
        file_key = (request.data.get('file_key') or '').strip()
        document, created = services.classer_document_apres_vente(
            company=request.user.company,
            file_key=file_key,
            nom=nom,
            source_type=source_type,
            source_id=source_id,
            cabinet=(request.data.get('cabinet') or 'Après-vente'),
            dossier=(request.data.get('dossier') or 'Après-vente'),
            description=(request.data.get('description') or ''),
            created_by=request.user,
        )
        # GED11/GED12 — indexe le document déposé (no-op sémantique sans clé).
        services.update_search_vector(document)
        services.index_embedding(document)
        return Response(
            DocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='semantique')
    def semantique(self, request):
        """GED12 — Recherche sémantique (pgvector), KEY-GATED no-op.

        `GET …/documents/semantique/?q=<texte>`. Quand la clé d'embedding est
        configurée, classe par proximité sémantique ; sinon dégrade proprement
        sur la recherche plein-texte GED11. `mode` indique le moteur utilisé."""
        query = request.query_params.get('q', '')
        qs = selectors.semantic_search_documents(request.user, query)
        data = DocumentSerializer(
            qs, many=True, context={'request': request}).data
        return Response({
            'mode': 'semantique' if services.embedding_enabled()
            else 'plein-texte',
            'results': data,
        })

    @action(detail=False, methods=['get'], url_path='recherche')
    def recherche(self, request):
        """GED11 — Recherche plein-texte Postgres (SearchVector + GIN).

        `GET …/documents/recherche/?q=<texte>` renvoie les documents visibles
        (ACL coffre-fort + société) dont le tsvector matche la requête, classés
        par pertinence. Réutilise `selectors.search_documents`."""
        query = request.query_params.get('q', '')
        qs = selectors.search_documents(request.user, query).select_related(
            'folder', 'coffre', 'created_by')
        page = self.paginate_queryset(qs)
        if page is not None:
            data = DocumentSerializer(
                page, many=True, context={'request': request}).data
            return self.get_paginated_response(data)
        data = DocumentSerializer(
            qs, many=True, context={'request': request}).data
        return Response(data)

    @action(detail=False, methods=['get'], url_path='docqa')
    def docqa(self, request):
        """FG352/XKB20 — Récupération RAG / DocQA : top-k fragments pour une
        question, GED + KB combinés.

        `GET …/documents/docqa/?q=<question>&k=<n>`. Renvoie les fragments de
        documents (`DocumentChunk`) les plus proches de la question (distance
        cosinus, magasin pgvector partagé), bornés aux documents visibles de
        l'utilisateur (ACL coffre-fort + société). KEY-GATED : sans clé
        d'embedding, `enabled` est faux et `results` est vide (no-op propre,
        aucun coût). Réutilise `selectors.retrieve_chunks`.

        XKB20 — les fragments d'articles de la base de connaissances
        (`apps.kb`) sont ÉGALEMENT récupérés, via `kb.selectors.retrieve_chunks`
        (JAMAIS les models/views de `kb` directement — lecture cross-app par
        selector, cf. CLAUDE.md) : ce sélecteur applique DÉJÀ les ACL KB (KB7 +
        XKB9) pour l'utilisateur courant, donc un article restreint n'est
        jamais cité pour un utilisateur non autorisé. Les deux jeux de
        fragments sont fusionnés et re-triés par distance croissante avant
        d'être tronqués à `k` — la meilleure source gagne, peu importe l'app
        d'origine."""
        from apps.kb import selectors as kb_selectors

        query = request.query_params.get('q', '')
        try:
            k = int(request.query_params.get('k', 5))
        except (TypeError, ValueError):
            k = 5
        chunks = selectors.retrieve_chunks(request.user, query, limit=k)
        results = [{
            'source': 'ged',
            'document': c.document_id,
            'document_nom': c.document.nom,
            'chunk_index': c.chunk_index,
            'texte': c.texte,
            'distance': getattr(c, 'distance', None),
        } for c in chunks]
        kb_chunks = kb_selectors.retrieve_chunks(request.user, query, limit=k)
        results += [{
            'source': 'kb',
            'article': c.article_id,
            'article_titre': c.article.titre,
            'chunk_index': c.chunk_index,
            'texte': c.texte,
            'distance': getattr(c, 'distance', None),
        } for c in kb_chunks]
        results.sort(key=lambda r: (
            r['distance'] if r['distance'] is not None else float('inf')))
        results = results[:k]
        return Response({
            'enabled': services.embedding_enabled(),
            'results': results,
        })

    @action(detail=True, methods=['post'], url_path='ocr-piece')
    def ocr_piece(self, request, pk=None):
        """GED33 — OCR ce document (pièce : CIN/facture/BL) → métadonnées typées.

        `POST …/documents/<id>/ocr-piece/` — corps optionnel
        `{type_piece?: 'cin'|'facture'|'bl'}` (sinon deviné). Récupère le binaire
        de la version courante, lance l'OCR (no-op sans clé) puis extrait des
        métadonnées par parsing LOCAL déterministe (aucune clé requise pour le
        parsing) et les fusionne ADDITIVEMENT dans `custom_data` (jamais
        d'écrasement). Le document est company-scopé via `get_object()`.
        Écriture : responsable/admin. Renvoie le document + `{metadonnees: {...},
        ocr_enabled: <bool>}`."""
        document = self.get_object()
        # GED23 — write-once : pas de mutation de custom_data si archivé (403).
        if document.est_archive_legalement:
            from .models import ARCHIVE_LEGALE_MESSAGE
            return Response({'detail': ARCHIVE_LEGALE_MESSAGE},
                            status=status.HTTP_403_FORBIDDEN)
        type_piece = (request.data.get('type_piece') or '').strip() or None
        version = (DocumentVersion.objects
                   .filter(document=document)
                   .order_by('-version').first())
        file_bytes = None
        mime = ''
        if version and version.file_key:
            file_bytes, _err = fetch_attachment(version.file_key)
            mime = version.mime or ''
        meta = services.ocr_piece_vers_metadonnees(
            document, file_bytes=file_bytes, mime=mime, type_piece=type_piece)
        document.refresh_from_db()
        services.update_search_vector(document)
        return Response({
            'document': DocumentSerializer(
                document, context={'request': request}).data,
            'metadonnees': meta,
            'ocr_enabled': services.ocr_enabled(),
        })

    @action(detail=True, methods=['post'], url_path='classer')
    def classer(self, request, pk=None):
        """GED34 — Classe automatiquement ce document (IA gated → heuristique).

        `POST …/documents/<id>/classer/` — aucun corps requis. Tente le provider
        IA (no-op sans clé) puis retombe sur l'heuristique locale (mots-clés) et
        pose ADDITIVEMENT `custom_data['categorie']` (jamais d'écrasement). Ne
        déplace ni ne supprime jamais le document. Le document est company-scopé
        via `get_object()`. Écriture : responsable/admin. Renvoie le document +
        `{categorie: <str>, ia_enabled: <bool>}`."""
        document = self.get_object()
        if document.est_archive_legalement:
            from .models import ARCHIVE_LEGALE_MESSAGE
            return Response({'detail': ARCHIVE_LEGALE_MESSAGE},
                            status=status.HTTP_403_FORBIDDEN)
        categorie = services.classer_document(document)
        document.refresh_from_db()
        services.update_search_vector(document)
        return Response({
            'document': DocumentSerializer(
                document, context={'request': request}).data,
            'categorie': categorie,
            'ia_enabled': services.classification_enabled(),
        })

    @action(detail=True, methods=['post'], url_path='deplacer')
    def deplacer(self, request, pk=None):
        """Déplace ce document dans un autre dossier (déplacement scopé société).

        Body : `{"folder": <id>}`. Le document source est company-scopé via
        `get_object()` (404 cross-société). Le dossier cible est résolu DANS la
        société courante — un id d'une autre société est introuvable (404). La
        société du document n'est jamais modifiée (posée côté serveur)."""
        document = self.get_object()
        raw_folder = request.data.get('folder', None)
        if raw_folder in (None, '', 'null'):
            return Response(
                {'folder': 'Le dossier cible est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        new_folder = (Folder.objects
                      .filter(company=request.user.company)
                      .filter(pk=raw_folder).first())
        if new_folder is None:
            return Response(
                {'folder': 'Dossier inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            services.move_document(document, new_folder)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        document.refresh_from_db()
        data = DocumentSerializer(document, context={'request': request}).data
        return Response(data)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """GED15 — Historique complet des versions d'un document (scopé société).

        `GET …/documents/<id>/historique/` renvoie toutes les versions du
        document, ordonnées de la plus récente à la plus ancienne (numéro
        décroissant). Le document est company-scopé via `get_object()` (404
        cross-société + ACL coffre). Lecture : tout rôle authentifié.

        Chaque entrée expose `restored_from_version` pour tracer les
        restaurations (GED15 : null pour les versions ordinaires, numéro source
        pour les restaurations)."""
        document = self.get_object()
        qs = selectors.versions_for_document(document).select_related(
            'uploaded_by', 'restored_from')
        data = DocumentVersionSerializer(
            qs, many=True, context={'request': request}).data
        return Response(data)

    @action(detail=True, methods=['post'], url_path='restaurer')
    def restaurer(self, request, pk=None):
        """GED15 — Restaure le document à une version antérieure (non destructif).

        `POST …/documents/<id>/restaurer/` — corps : `{"version": <id>}`.

        Crée une NOUVELLE version (numéro max + 1) dont le contenu est copié
        depuis la version `version`, et marque `restored_from` → source.
        L'historique est entièrement PRÉSERVÉ : aucune version n'est modifiée
        ou supprimée (opération additive et auditée). La version source est
        bornée à ce document et à la société courante (jamais cross-société ni
        cross-document). Écriture : responsable/admin."""
        document = self.get_object()
        version_id = request.data.get('version')
        if not version_id:
            return Response(
                {'version': 'L\'identifiant de version est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        # La version source est bornée à ce document et à la société courante.
        source_version = (DocumentVersion.objects
                          .filter(company=request.user.company,
                                  document=document,
                                  pk=version_id)
                          .first())
        if source_version is None:
            return Response(
                {'version': 'Version inconnue ou inaccessible.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            new_version = services.restore_version(
                document, source_version, uploaded_by=request.user)
        except ArchivageLegalError as exc:
            # GED23 — document archivé légalement : write-once, pas de restauration.
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DocumentVersionSerializer(
                new_version, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    def _get_corbeille_object(self, request, pk):
        """GED26 — Récupère un document EN CORBEILLE borné à la société/ACL.

        `get_object()` s'appuie sur `get_queryset()` qui EXCLUT la corbeille ; les
        actions de restauration/purge doivent au contraire cibler les documents
        soft-supprimés. On résout donc le pk dans `documents_corbeille` (même
        ACL coffre + société) — un document absent (autre société / pas en
        corbeille) renvoie None (→ 404, jamais de fuite cross-société)."""
        return selectors.documents_corbeille(request.user).filter(pk=pk).first()

    @action(detail=False, methods=['get'], url_path='corbeille')
    def corbeille(self, request):
        """GED26 — Liste les documents EN CORBEILLE (soft-supprimés) de la société.

        `GET …/documents/corbeille/`. Renvoie uniquement les documents mis en
        corbeille (`supprime_le` renseigné), bornés à la société et à l'ACL
        coffre-fort (GED8) de l'utilisateur. Paginé comme la liste standard."""
        qs = (selectors.documents_corbeille(request.user)
              .select_related('folder', 'coffre', 'created_by', 'supprime_par')
              .order_by('-supprime_le', 'nom'))
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = DocumentSerializer(
                page, many=True, context={'request': request})
            return self.get_paginated_response(ser.data)
        ser = DocumentSerializer(qs, many=True, context={'request': request})
        return Response(ser.data)

    @action(detail=True, methods=['get'], url_path='journal-acces')
    def journal_acces(self, request, pk=None):
        """GED35 — Journal d'accès EN LECTURE de ce document (audit).

        `GET …/documents/<id>/journal-acces/`. Liste les accès tracés (aperçu /
        téléchargement / public / consultation) du document, bornés à la société.
        Lecture réservée aux responsables/admins (l'audit est sensible). Paginé
        comme la liste standard."""
        document = self.get_object()
        qs = selectors.journal_acces_for_company(
            request.user.company, document=document)
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = JournalAccesSerializer(
                page, many=True, context={'request': request})
            return self.get_paginated_response(ser.data)
        ser = JournalAccesSerializer(qs, many=True, context={'request': request})
        return Response(ser.data)

    @action(detail=True, methods=['post'], url_path='mettre-en-corbeille')
    def mettre_en_corbeille(self, request, pk=None):
        """GED26 — Met ce document dans la CORBEILLE (soft-delete réversible).

        `POST …/documents/<id>/mettre-en-corbeille/`. Le document disparaît des
        listes par défaut mais reste récupérable (`restaurer-corbeille`).
        REFUS (403, jamais 500) si le document est archivé légalement (GED23,
        write-once) ou sous rétention légale active (GED24, legal hold) — mêmes
        gardes que la suppression. IDEMPOTENT. Écriture : responsable/admin."""
        document = self.get_object()
        try:
            services.mettre_en_corbeille(document, request.user)
        except (ArchivageLegalError, LegalHoldError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        document.refresh_from_db()
        return Response(
            DocumentSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='restaurer-corbeille')
    def restaurer_corbeille(self, request, pk=None):
        """GED26 — Restaure ce document DEPUIS la corbeille (annule le soft-delete).

        `POST …/documents/<id>/restaurer-corbeille/`. Vide `supprime_le` : le
        document réapparaît dans les listes. Le document cible est résolu dans la
        corbeille de la société (un document absent / d'une autre société → 404).
        IDEMPOTENT. Écriture : responsable/admin.

        NB : distinct de `restaurer` (GED15) qui restaure une VERSION antérieure
        d'un document vivant ; ici on sort le DOCUMENT de la corbeille."""
        document = self._get_corbeille_object(request, pk)
        if document is None:
            return Response(
                {'detail': 'Document introuvable dans la corbeille.'},
                status=status.HTTP_404_NOT_FOUND)
        services.restaurer_de_corbeille(document)
        document.refresh_from_db()
        return Response(
            DocumentSerializer(document, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='purger')
    def purger(self, request, pk=None):
        """GED26 — Supprime DÉFINITIVEMENT ce document depuis la corbeille (réel).

        `POST …/documents/<id>/purger/`. Effacement RÉEL et irréversible — exige
        que le document soit DÉJÀ dans la corbeille (sinon 400). Les gardes
        légales restent respectées : archivage légal (GED23) ou legal hold actif
        (GED24) → 403 (jamais 500). Le document cible est résolu dans la
        corbeille de la société (autre société / vivant → 404). Écriture :
        responsable/admin."""
        document = self._get_corbeille_object(request, pk)
        if document is None:
            return Response(
                {'detail': 'Document introuvable dans la corbeille.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            services.purger_definitivement(document)
        except (ArchivageLegalError, LegalHoldError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='check-out')
    def check_out(self, request, pk=None):
        """GED16 — Extrait un document (pose le verrou de check-out).

        `POST …/documents/<id>/check-out/` — aucun corps requis.

        Si le document est libre, il est verrouillé pour l'utilisateur courant.
        Si le document est déjà extrait PAR LE MÊME utilisateur, idempotent (200).
        Si extrait par un autre utilisateur, renvoie 409 Conflict.
        """
        document = self.get_object()
        try:
            doc = services.checkout_document(document, request.user)
        except PermissionError as exc:
            # GED23 : check-out d'un document archivé légalement (write-once) →
            # checkout_document lève PermissionError → 409 (bloqué, immuable).
            return Response(
                {'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        doc.refresh_from_db()
        return Response(
            DocumentSerializer(doc, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='check-in')
    def check_in(self, request, pk=None):
        """GED16 — Libère le verrou d'un document (check-in).

        `POST …/documents/<id>/check-in/` — aucun corps requis.

        Seul le détenteur du verrou OU un administrateur peut libérer le verrou.
        Si le document est déjà libre, idempotent (200).
        """
        document = self.get_object()
        try:
            doc = services.checkin_document(document, request.user)
        except ArchivageLegalError as exc:
            # GED23 — document archivé légalement : write-once, save() bloqué.
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        doc.refresh_from_db()
        return Response(
            DocumentSerializer(doc, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='verrouiller')
    def verrouiller(self, request, pk=None):
        """ZGED9 — Pose le verrou d'AVERTISSEMENT léger (« en cours
        d'édition »), DISTINCT du check-out GED16 : n'empêche jamais la
        lecture, affiche un bandeau à tous. Body optionnel :
        `{"motif": "..."}`. 409 si déjà posé par un autre utilisateur."""
        document = self.get_object()
        try:
            doc = services.verrouiller_avertissement(
                document, request.user, motif=request.data.get('motif', ''))
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        doc.refresh_from_db()
        return Response(
            DocumentSerializer(doc, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='deverrouiller')
    def deverrouiller(self, request, pk=None):
        """ZGED9 — Lève le verrou d'AVERTISSEMENT. Le poseur OU un
        gestionnaire/admin peut lever (le forçage par un tiers gestionnaire
        est journalisé). Idempotent si déjà libre."""
        document = self.get_object()
        try:
            doc = services.deverrouiller_avertissement(document, request.user)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        doc.refresh_from_db()
        return Response(
            DocumentSerializer(doc, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='office-ouvrir')
    def office_ouvrir(self, request, pk=None):
        """XGED30 — Ouvre ce document Office dans l'éditeur embarqué (slot
        Collabora/OnlyOffice, key-gated).

        `POST …/documents/<id>/office-ouvrir/` — sans `GED_OFFICE_URL`
        configuré : 400 explicite (aucune UI, aucun appel). Avec l'URL posée :
        pose le check-out (GED16) et renvoie `{"editor_url", "document_id"}`.
        Gardes GED23/24 respectées (403). Écriture : responsable/admin (même
        motif que check-out — ouvrir en édition verrouille le document)."""
        document = self.get_object()
        try:
            data = services.ouvrir_dans_editeur_office(
                document, user=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (ArchivageLegalError, LegalHoldError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(data)

    @action(detail=True, methods=['post'], url_path='office-sauvegarder',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def office_sauvegarder(self, request, pk=None):
        """XGED30 — Callback de sauvegarde de l'éditeur Office : crée une
        NOUVELLE version depuis le contenu édité.

        `POST …/documents/<id>/office-sauvegarder/` — corps multipart
        `{"file": <fichier>}`. Sans `GED_OFFICE_URL` : 400 explicite. Respecte
        le check-out (un tiers ne peut pas écraser la session d'un autre —
        409) et les gardes GED23/24 (403). Écriture : responsable/admin."""
        document = self.get_object()
        upload = request.FILES.get('file')
        if upload is None:
            return Response(
                {'file': 'Un fichier est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            version = services.sauvegarder_depuis_editeur_office(
                document, contenu_bytes=upload.read(), user=request.user,
                filename=upload.name, mime=upload.content_type or '')
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except (ArchivageLegalError, LegalHoldError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        data = DocumentVersionSerializer(
            version, context={'request': request}).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='cycle-vie')
    def cycle_vie(self, request, pk=None):
        """GED17 — Fait avancer le document dans son cycle de vie documentaire.

        `POST …/documents/<id>/cycle-vie/` — corps : `{"statut": "<cible>"}`.

        Les statuts sont LOCAUX à la GED (brouillon → revue → approuvé →
        archivé → obsolète) et SÉPARÉS du funnel commercial `STAGES.py`. La
        transition est gardée côté serveur par la machine à états
        (`services.change_lifecycle_status`) : une transition non autorisée ou
        un statut inconnu renvoie 400. Le document est company-scopé (+ ACL
        coffre) via `get_object()`. Écriture : responsable/admin.
        """
        document = self.get_object()
        target = request.data.get('statut')
        if not target:
            return Response(
                {'statut': 'Le statut cible est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            doc = services.change_lifecycle_status(
                document, target, user=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        doc.refresh_from_db()
        return Response(
            DocumentSerializer(doc, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='demander-revue')
    def demander_revue(self, request, pk=None):
        """GED18 — Lance une demande d'approbation/revue sur ce document.

        `POST …/documents/<id>/demander-revue/` — corps optionnel :
        `{"approbateur": <id?>, "commentaire": "<str?>"}`.

        Crée une `DemandeApprobation` « en_attente » (demandeur + company posés
        côté serveur) et, si le document est brouillon, le fait avancer
        « brouillon → revue » via la machine à états GED17 (réutilisée, jamais
        dupliquée). `approbateur` est borné à la société courante. Une 2e demande
        alors qu'une est déjà en attente renvoie 400. Écriture : responsable/admin.
        """
        document = self.get_object()
        approbateur = None
        raw_approbateur = request.data.get('approbateur')
        if raw_approbateur not in (None, '', 'null'):
            from django.contrib.auth import get_user_model
            approbateur = (get_user_model().objects
                           .filter(company=request.user.company,
                                   pk=raw_approbateur)
                           .first())
            if approbateur is None:
                return Response(
                    {'approbateur': 'Approbateur inconnu.'},
                    status=status.HTTP_404_NOT_FOUND)
        try:
            # XGED20 — un approbateur EXPLICITE (choix manuel) surclasse tout
            # routage automatique (comportement GED18 inchangé). Sans
            # approbateur explicite, on consulte D'ABORD les règles de
            # routage conditionnel (rétrocompatible : sans règle applicable,
            # `request_review_avec_routage` délègue à `request_review`).
            if approbateur is not None:
                demande = services.request_review(
                    document, user=request.user, approbateur=approbateur,
                    commentaire=(request.data.get('commentaire') or '').strip())
            else:
                demande = services.request_review_avec_routage(
                    document, user=request.user,
                    commentaire=(request.data.get('commentaire') or '').strip())
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            DemandeApprobationSerializer(
                demande, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='demandes')
    def demandes(self, request, pk=None):
        """GED18 — Demandes d'approbation/revue de ce document (récentes d'abord).

        `GET …/documents/<id>/demandes/`. Le document est company-scopé (+ ACL
        coffre) via `get_object()`. Lecture : tout rôle authentifié."""
        document = self.get_object()
        qs = selectors.demandes_approbation_for_document(document).select_related(
            'demandeur', 'approbateur', 'document')
        data = DemandeApprobationSerializer(
            qs, many=True, context={'request': request}).data
        return Response(data)

    @action(detail=True, methods=['post'], url_path='archiver-legalement')
    def archiver_legalement(self, request, pk=None):
        """GED23 — Archive ce document à VALEUR PROBANTE (write-once / object-lock).

        `POST …/documents/<id>/archiver-legalement/` — corps optionnel :
        `{"motif": "<str?>", "retain_until": "<YYYY-MM-DD?>"}`.

        Pose un `ArchivageLegal` qui rend le document (et ses versions) IMMUABLE
        (write-once) : plus aucune modification ni suppression ensuite. Le
        condensat d'intégrité (SHA-256) de la version courante est figé comme
        preuve d'intégrité, et — en BONUS best-effort — un verrou objet
        (object-lock retain-until) est tenté côté stockage (dégrade proprement
        si non supporté). `company` et `archive_par` sont posés CÔTÉ SERVEUR
        (jamais lus du corps). Un document déjà archivé renvoie 400. Écriture :
        responsable/admin."""
        document = self.get_object()
        # `retain_until` optionnel — date du verrou objet (YYYY-MM-DD).
        retain_until = None
        raw_retain = request.data.get('retain_until')
        if raw_retain not in (None, '', 'null'):
            from django.utils.dateparse import parse_date
            retain_until = parse_date(str(raw_retain))
            if retain_until is None:
                return Response(
                    {'retain_until': 'Date invalide (format attendu : '
                                     'AAAA-MM-JJ).'},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            archivage = services.archiver_legalement(
                document, user=request.user,
                motif=(request.data.get('motif') or '').strip(),
                retain_until=retain_until)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            ArchivageLegalSerializer(
                archivage, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='placer-legal-hold')
    def placer_legal_hold(self, request, pk=None):
        """GED24 — Place une RÉTENTION LÉGALE (legal hold) sur ce document.

        `POST …/documents/<id>/placer-legal-hold/` — corps optionnel :
        `{"motif": "<str?>"}`. Gèle la suppression/purge du document tant que le
        hold reste actif (le document reste éditable — seul l'effacement est
        gelé), surclassant toute purge de politique de rétention (GED22).
        `company` et `place_par` sont posés CÔTÉ SERVEUR (jamais lus du corps).
        IDEMPOTENT : un hold actif existant est renvoyé tel quel (pas de
        doublon). Écriture : responsable/admin."""
        document = self.get_object()
        try:
            hold = services.placer_legal_hold(
                document, user=request.user,
                motif=(request.data.get('motif') or '').strip())
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            LegalHoldSerializer(hold, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='lever-legal-hold')
    def lever_legal_hold(self, request, pk=None):
        """GED24 — Lève la/les rétention(s) légale(s) active(s) de ce document.

        `POST …/documents/<id>/lever-legal-hold/`. Bascule tout legal hold actif
        en levé (trace `date_levee`/`leve_par` côté serveur — l'historique est
        conservé, jamais supprimé). Le document redevient supprimable une fois
        le dernier hold actif levé (sauf autre protection, ex. GED23).
        IDEMPOTENT : sans hold actif, renvoie simplement `leves: 0`. Écriture :
        responsable/admin."""
        document = self.get_object()
        try:
            leves = services.lever_legal_hold(document, user=request.user)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({'leves': leves}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='caviarder')
    def caviarder(self, request, pk=None):
        """XGED24 — Caviarde des zones du document sur une COPIE publiée
        (l'original reste intact).

        Corps : `{"zones": [{"page": <int 0-based>, "x0", "y0", "x1", "y1"
        (%)}], "version": <id?>}`. Le texte sous les zones est SUPPRIMÉ (pas
        un simple rectangle) via PyMuPDF (import gardé — 400 explicite sans
        la lib). La copie devient un nouveau document lié à l'original via
        `custom_data.caviarde_depuis`. Écriture : responsable/admin."""
        document = self.get_object()
        version_id = request.data.get('version')
        version = (selectors.latest_version(document) if not version_id else
                   DocumentVersion.objects.filter(
                       company=request.user.company, document=document,
                       pk=version_id).first())
        if version is None:
            return Response(
                {'detail': 'Aucune version disponible pour le caviardage.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            new_doc = services.caviarder_document(
                version, request.data.get('zones') or [],
                created_by=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = DocumentSerializer(new_doc, context={'request': request}).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='scinder')
    def scinder(self, request, pk=None):
        """XGED10 — Scinde ce document en segments (chaque segment = un nouveau
        `Document`). Corps : `{"points_de_coupe": [<int>, ...], "version": <id?>}`.

        Sans PyMuPDF installé sur le serveur : 400 explicite (jamais un split
        silencieusement faux). Respecte les gardes GED23/24 (archivé/hold →
        403). Écriture : responsable/admin."""
        document = self.get_object()
        version_id = request.data.get('version')
        version = (selectors.latest_version(document) if not version_id else
                   DocumentVersion.objects.filter(
                       company=request.user.company, document=document,
                       pk=version_id).first())
        if version is None:
            return Response(
                {'detail': 'Aucune version disponible pour la scission.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            created = services.scinder_pdf(
                version, request.data.get('points_de_coupe') or [])
        except (ArchivageLegalError, LegalHoldError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        data = DocumentSerializer(
            created, many=True, context={'request': request}).data
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='fusionner')
    def fusionner(self, request):
        """XGED10 — Fusionne plusieurs documents PDF (ordonnés) en un seul.

        Corps : `{"documents": [<id>, ...], "cible": <id?>, "nom": "<str?>"}`.
        Sans `cible`, crée un nouveau document (dans le dossier du 1er de la
        liste) ; avec `cible`, ajoute une nouvelle version à ce document
        existant. Tous les documents sources ET la cible sont bornés à la
        société courante. Sans PyMuPDF : 400 explicite. Écriture :
        responsable/admin."""
        # request.data peut être un QueryDict (multipart/form) où `.get()` ne
        # renvoie que la DERNIÈRE valeur d'une clé répétée : `.getlist()`
        # restitue la liste complète. Un corps JSON (dict simple) n'a pas
        # `.getlist()`, d'où le fallback sur `.get()`.
        if hasattr(request.data, 'getlist'):
            ids = request.data.getlist('documents') or []
        else:
            ids = request.data.get('documents') or []
        if not ids or len(ids) < 2:
            return Response(
                {'documents': 'Au moins deux documents sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        qs = {d.pk: d for d in selectors.documents_visible_to_user(
            request.user).filter(pk__in=ids)}
        try:
            documents_ordonnes = [qs[int(i)] for i in ids]
        except (KeyError, ValueError):
            return Response(
                {'documents': 'Un ou plusieurs documents sont inconnus.'},
                status=status.HTTP_404_NOT_FOUND)
        cible = None
        cible_id = request.data.get('cible')
        if cible_id:
            cible = selectors.documents_visible_to_user(
                request.user).filter(pk=cible_id).first()
            if cible is None:
                return Response(
                    {'cible': 'Document cible inconnu.'},
                    status=status.HTTP_404_NOT_FOUND)
        try:
            resultat = services.fusionner_pdf(
                documents_ordonnes, cible=cible,
                company=request.user.company,
                nom=(request.data.get('nom') or '').strip(),
                created_by=request.user)
        except (ArchivageLegalError, LegalHoldError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DocumentSerializer(resultat, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='comparer')
    def comparer(self, request, pk=None):
        """XGED17 — Compare deux versions d'un document.

        `GET …/documents/<id>/comparer/?v1=<id>&v2=<id>`. Renvoie toujours le
        diff de MÉTADONNÉES (taille, checksum, auteur, custom_data champ à
        champ) et, quand les deux versions ont un texte plein-texte/OCR
        (GED11/12), le diff textuel unifié (`difflib`) ; sinon un message
        « comparaison binaire indisponible ». Les deux versions sont bornées à
        ce document et à la société courante. Lecture : tout rôle authentifié."""
        document = self.get_object()
        v1_id, v2_id = request.query_params.get('v1'), request.query_params.get('v2')
        if not v1_id or not v2_id:
            return Response(
                {'detail': 'Les paramètres v1 et v2 sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        versions = {
            v.pk: v for v in DocumentVersion.objects.filter(
                company=request.user.company, document=document,
                pk__in=[v1_id, v2_id])
        }
        try:
            v1, v2 = versions[int(v1_id)], versions[int(v2_id)]
        except (KeyError, ValueError):
            return Response(
                {'detail': 'Version inconnue ou inaccessible.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(selectors.comparer_versions(v1, v2))

    @action(detail=False, methods=['post'], url_path='operations-lot')
    def operations_lot(self, request):
        """XGED14 — Opération par LOT sur une multi-sélection de documents.

        Corps : `{"documents": [<id>, ...], "operation": "<str>", "params": {}}`.
        Opérations : `tagger`/`detaguer`/`deplacer`/`corbeille`/`telecharger_zip`/
        `partager`/`demander_signature`/`demander_revue`. Chaque item est validé
        INDIVIDUELLEMENT (gardes GED23/24 par document) — un item bloqué est
        rapporté dans `erreurs` SANS jamais faire échouer le reste (jamais
        tout-ou-rien silencieux). `telecharger_zip` renvoie directement un ZIP
        binaire ; les autres opérations renvoient un rapport JSON. Écriture :
        responsable/admin (sauf `telecharger_zip`, lecture)."""
        ids = request.data.get('documents') or []
        operation = request.data.get('operation')
        params = request.data.get('params') or {}
        if not ids or not operation:
            return Response(
                {'detail': 'documents et operation sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        qs = selectors.documents_visible_to_user(request.user).filter(pk__in=ids)
        documents = list(qs)
        if operation == 'telecharger_zip':
            zip_bytes, erreurs = services.zipper_documents(documents)
            response = HttpResponse(zip_bytes, content_type='application/zip')
            response['Content-Disposition'] = (
                'attachment; filename="documents.zip"')
            return response
        resultats, erreurs = services.operation_lot(
            documents, operation=operation, params=params, user=request.user)
        return Response({'resultats': resultats, 'erreurs': erreurs})

    @action(detail=True, methods=['post'], url_path='planifier')
    def planifier(self, request, pk=None):
        """XGED15 — Planifie une activité sur ce document (« relancer le J+7 »).

        Corps : `{"libelle": "<str>", "echeance": "AAAA-MM-JJ", "assigne_a": <id?>}`.
        `company`/`created_by` posés côté serveur. Écriture : responsable/admin."""
        document = self.get_object()
        libelle = (request.data.get('libelle') or '').strip()
        echeance = request.data.get('echeance')
        if not libelle or not echeance:
            return Response(
                {'detail': 'libelle et echeance sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        assigne_a = None
        raw_assigne = request.data.get('assigne_a')
        if raw_assigne:
            from django.contrib.auth import get_user_model
            assigne_a = get_user_model().objects.filter(
                company=request.user.company, pk=raw_assigne).first()
        try:
            planif = services.planifier_document(
                document, libelle=libelle, echeance=echeance,
                assigne_a=assigne_a, created_by=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        from .serializers import PlanificationDocumentSerializer
        return Response(
            PlanificationDocumentSerializer(
                planif, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='timeline')
    def timeline(self, request, pk=None):
        """XGED15 — Timeline du document : mêle le journal auto
        (`DocumentActivity`) et les notes/@mentions (`records.Comment`, via le
        chatter FG7 réutilisé — pas de système parallèle). Lecture : tout rôle
        authentifié."""
        document = self.get_object()
        data = selectors.timeline_document(document)
        return Response(data)

    @action(detail=True, methods=['get'], url_path='permissions-effectives',
            renderer_classes=[JSONRenderer, BrowsableAPIRenderer, _CsvOrJSONRenderer])
    def permissions_effectives(self, request, pk=None):
        """XGED22 — Rapport de permissions effectives (« qui voit ce document
        et pourquoi »).

        `GET documents/<id>/permissions-effectives/` — pour chaque
        utilisateur de la société, le niveau résolu par `acl_effective`
        (GED19) avec sa JUSTIFICATION : override direct sur le document,
        héritage d'un dossier ancêtre, règle par métadonnée (XGED21) ou
        admin. `?format=csv` exporte le même rapport en CSV pour audit.
        Gestion/admin uniquement (403 pour tout autre rôle)."""
        document = self.get_object()
        lignes = selectors.permissions_effectives(document)
        if request.query_params.get('format') == 'csv':
            return _permissions_effectives_csv(lignes, f'document-{document.pk}')
        return Response({'lignes': lignes})


class DocumentVersionViewSet(TenantMixin, viewsets.ModelViewSet):
    """Versions d'un document. Le numéro de version et `uploaded_by` sont posés
    côté serveur via `services.add_version` ; `checksum` permet la dédup."""
    queryset = DocumentVersion.objects.select_related(
        'document', 'uploaded_by').all()
    serializer_class = DocumentVersionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['version', 'created_at']

    def get_permissions(self):
        # ``apercu`` est une opération de LECTURE (aperçu inline même-origine),
        # donc ouverte à tout rôle authentifié comme list/retrieve — même motif
        # que les actions de lecture custom des viewsets frères.
        if self.action in READ_ACTIONS or self.action == 'apercu':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        return qs

    def perform_create(self, serializer):
        # Numéro de version auto-incrémenté + company/uploaded_by côté serveur.
        document = serializer.validated_data['document']
        # XGED18 — un document-lien (URL externe) refuse toute version fichier.
        try:
            services.assert_not_document_lien(document, action='ajout de version')
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': str(exc)})
        # GED23 — write-once : on n'ajoute jamais de version à un document
        # archivé légalement (immuable). Refus TÔT avec un message clair (403).
        try:
            services.assert_not_archive_legalement(document)
        except ArchivageLegalError as exc:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(str(exc))
        # GED16 — bloque l'ajout d'une version si le document est extrait par
        # un autre utilisateur.
        try:
            services.assert_not_locked_by_other(document, self.request.user)
        except PermissionError as exc:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(str(exc))
        v = serializer.validated_data
        instance = services.add_version(
            document,
            file_key=v['file_key'],
            company=self.request.user.company,
            filename=v.get('filename', ''),
            size=v.get('size', 0),
            mime=v.get('mime', ''),
            checksum=v.get('checksum', ''),
            uploaded_by=self.request.user,
        )
        serializer.instance = instance

    @action(detail=True, methods=['get'], url_path='apercu')
    def apercu(self, request, pk=None):
        """GED14 — Proxy même-origine pour l'aperçu inline multi-format.

        Relaie le contenu binaire de la version via Django (MÊME ORIGINE) au
        lieu d'une URL présignée pointant vers l'hôte interne MinIO (injoignable
        depuis le navigateur). Permet l'ouverture inline de PDF, images et
        textes directement dans le navigateur (pas de téléchargement forcé).

        La version est bornée à la société courante (TenantMixin + scoping du
        document parent) : une version d'une autre société renvoie 404. Lecture
        : tout rôle authentifié.

        Types pris en charge en aperçu inline :
        - PDF       (application/pdf)
        - Images    (image/png, image/jpeg, image/webp, image/gif)
        - Texte     (text/plain, text/csv, text/html)
        Tout autre type est servi avec `Content-Disposition: attachment` (pas
        d'aperçu inline, téléchargement direct sécurisé).
        """
        version = self.get_object()  # borné à la société par get_queryset (TenantMixin)
        data, err = fetch_attachment(version.file_key)
        if err:
            return Response({'detail': err}, status=status.HTTP_404_NOT_FOUND)

        mime = version.mime or 'application/octet-stream'
        safe_name = (version.filename or 'document').replace('"', '')

        # GED21 — Contrôle de diffusion : si le document est marqué
        # `watermark_diffusion`, on filigrane le CONTENU SERVI (best-effort,
        # dégrade à l'original si la lib manque). Le flux reste byte-identique
        # quand le drapeau est faux. Le filigrane est purement de rendu — le
        # binaire stocké et le statut documentaire ne changent jamais.
        document = version.document
        if getattr(document, 'watermark_diffusion', False):
            label = services.watermark_label(
                company=document.company, user=request.user)
            data, marked = services.apply_watermark(data, mime, label)
            if marked and mime in services._WATERMARK_IMAGE_MIMES:
                # Les images filigranées sont réémises en PNG (alpha préservé).
                mime = 'image/png'

        disposition = (
            'inline' if mime in _INLINE_MIMES else 'attachment'
        )

        # GED35 — journalise l'accès EN LECTURE (best-effort, ne bloque jamais).
        from .models import ACCES_APERCU, ACCES_TELECHARGEMENT
        services.journaliser_acces(
            document, utilisateur=request.user,
            type_acces=(ACCES_APERCU if disposition == 'inline'
                        else ACCES_TELECHARGEMENT),
            adresse_ip=services._adresse_ip_requete(request))

        resp = HttpResponse(data, content_type=mime)
        resp['Content-Disposition'] = f'{disposition}; filename="{safe_name}"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp


class DocumentLienViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED6 — Liens polymorphes Document ↔ objet métier (records.ALLOWED_TARGETS).

    Création : `{"document": <id>, "model": "ventes.devis", "id": <pk>}`. La
    cible est résolue + validée par `records.resolve_target` (type autorisé ET
    objet de la société courante) — un type non autorisé ou une cible hors
    société est rejeté en 400. `document` est borné à la société (404 sinon),
    `company` est posée côté serveur (cohérente avec le document).

    Reverse lookup — documents rattachés à un objet donné :
    `GET …/liens/?model=ventes.devis&id=<pk>` filtre les liens sur cette cible.
    Liste sans filtre : tous les liens de la société.
    """
    queryset = DocumentLien.objects.select_related(
        'document', 'content_type', 'created_by').all()
    serializer_class = DocumentLienSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        # Reverse lookup : tous les documents liés à (model, id).
        model = self.request.query_params.get('model')
        oid = self.request.query_params.get('id')
        if model and oid:
            try:
                ct, _ = resolve_target(
                    model, oid, self.request.user.company)
            except ValueError:
                return qs.none()
            qs = qs.filter(content_type=ct, object_id=oid)
        return qs

    def create(self, request, *args, **kwargs):
        company = request.user.company
        # 1) cible polymorphe : type autorisé + objet de la société.
        try:
            ct, _obj = resolve_target(
                request.data.get('model'), request.data.get('id'), company)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        # 2) document : borné à la société (jamais lié à un doc d'une autre).
        doc_id = request.data.get('document')
        if not doc_id:
            return Response({'document': 'Document requis.'},
                            status=status.HTTP_400_BAD_REQUEST)
        document = Document.objects.filter(
            company=company, pk=doc_id).first()
        if document is None:
            return Response({'document': 'Document inconnu.'},
                            status=status.HTTP_404_NOT_FOUND)
        # 3) lien idempotent (un doc ne se lie qu'une fois à un objet donné).
        lien, created = DocumentLien.objects.get_or_create(
            document=document, content_type=ct,
            object_id=request.data.get('id'),
            defaults={'company': company, 'created_by': request.user})
        code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(DocumentLienSerializer(lien).data, status=code)


class DocumentTagViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED9 — Taxonomie de tags documentaires (hiérarchique, scopée société).

    Lecture : tout rôle (les formulaires/filtres en ont besoin). Écriture :
    responsable/admin. `company` posée côté serveur. Filtre `?parent=<id|null>`
    pour naviguer la taxonomie ; action `documents` liste les documents portant
    ce tag (option `?descendants=1` pour inclure les sous-tags)."""
    queryset = DocumentTag.objects.select_related('parent').all()
    serializer_class = DocumentTagSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'slug', 'description']
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'documents':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        parent = self.request.query_params.get('parent')
        if parent == 'null':
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'], url_path='documents')
    def documents(self, request, pk=None):
        """Documents portant ce tag (ACL coffre appliquée). `?descendants=1`
        inclut les documents des sous-tags de la taxonomie."""
        tag = self.get_object()
        include = request.query_params.get('descendants') in ('1', 'true')
        docs = selectors.documents_with_tag(tag, include_descendants=include)
        # Recroise avec l'ACL coffre-fort (un tag ne contourne pas le coffre).
        visible = selectors.documents_visible_to_user(request.user)
        docs = docs.filter(pk__in=visible.values('pk'))
        data = DocumentSerializer(
            docs, many=True, context={'request': request}).data
        return Response(data)


class DocumentTagAssignmentViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED9 — Affectations tag↔document (M2M explicite, scopé société).

    Création : `{"document": <id>, "tag": <id>}` (idempotent via la contrainte
    d'unicité). `company`/`created_by` posés côté serveur. Filtrable par
    `?document=<id>` ou `?tag=<id>`."""
    queryset = DocumentTagAssignment.objects.select_related(
        'document', 'tag', 'created_by').all()
    serializer_class = DocumentTagAssignmentSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        tag = self.request.query_params.get('tag')
        if tag:
            qs = qs.filter(tag_id=tag)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class DemandeApprobationViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """GED18 — Workflow d'approbation / revue documentaire (scopé société).

    Lecture seule en CRUD : une demande est CRÉÉE via
    `documents/<id>/demander-revue/` et DÉCIDÉE via les actions `approuver` /
    `rejeter` (jamais par un POST/PATCH brut) — toujours côté serveur (company,
    demandeur, approbateur, statut, horodatage). Filtrable par `?document=<id>`,
    `?statut=…` et `?en_attente=1`.

    Lecture : tout rôle authentifié. Décision (approuver/rejeter) :
    responsable/admin. À l'approbation, le document « en revue » est avancé
    « revue → approuvé » via la machine à états GED17 (réutilisée, jamais
    dupliquée) ; au rejet, il repart « revue → brouillon ».
    """
    queryset = DemandeApprobation.objects.select_related(
        'document', 'demandeur', 'approbateur').all()
    serializer_class = DemandeApprobationSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'decision_le', 'statut']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        if self.request.query_params.get('en_attente') in ('1', 'true'):
            from .models import APPROBATION_EN_ATTENTE
            qs = qs.filter(statut=APPROBATION_EN_ATTENTE)
        return qs

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        """GED18 — Approuve cette demande et avance le document (revue→approuvé).

        `POST …/demandes-approbation/<id>/approuver/` — corps optionnel :
        `{"commentaire": "<str?>"}`. Une demande déjà décidée renvoie 400.
        Écriture : responsable/admin."""
        demande = self.get_object()
        try:
            # XGED20 — avance la chaîne séquentielle si une règle de routage
            # s'applique (sinon délègue directement à `approve_demande`,
            # comportement GED18 inchangé).
            dem = services.avancer_chaine_approbation_ged(
                demande, user=request.user,
                commentaire=(request.data.get('commentaire') or '').strip())
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        dem.refresh_from_db()
        return Response(
            DemandeApprobationSerializer(
                dem, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """GED18 — Rejette cette demande et renvoie le document en correction.

        `POST …/demandes-approbation/<id>/rejeter/` — corps optionnel :
        `{"commentaire": "<str?>"}`. Si le document est « en revue », il repart
        « revue → brouillon ». Une demande déjà décidée renvoie 400. Écriture :
        responsable/admin."""
        demande = self.get_object()
        try:
            dem = services.reject_demande(
                demande, user=request.user,
                commentaire=(request.data.get('commentaire') or '').strip())
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        dem.refresh_from_db()
        return Response(
            DemandeApprobationSerializer(
                dem, context={'request': request}).data)


class PartageGedViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED20 — CRUD de gestion des partages publics tokenisés (scopé société).

    Côté GESTION uniquement (créer, lister, révoquer) — l'accès public au
    document passe par l'endpoint token-only `public_partage` (AllowAny), jamais
    par ce viewset. `company` et `created_by` sont posés côté serveur (jamais
    lus du corps) ; `document` est borné à la société courante. Le `token` est
    généré côté serveur. Le mot de passe se pose via le champ `password`
    (write-only) — jamais renvoyé en clair.

    Lecture : tout rôle authentifié (un responsable suit ses partages).
    Création/modification/révocation : responsable/admin.
    """
    queryset = PartageGed.objects.select_related(
        'document', 'created_by', 'company').all()
    serializer_class = PartageGedSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'expires_at', 'telechargements']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = selectors.partages_for_company(
            self.request.user.company).select_related(
            'document', 'created_by', 'company')
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false'):
            qs = qs.filter(actif=False)
        return qs

    def perform_create(self, serializer):
        # company + created_by posés côté serveur (jamais du corps). Le document
        # est validé company-scopé dans le serializer (`validate_document`).
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='revoquer')
    def revoquer(self, request, pk=None):
        """GED20 — Révoque ce partage (kill-switch : actif=False).

        `POST …/partages/<id>/revoquer/`. Le partage est company-scopé via
        `get_object()` (404 cross-société). Après révocation, l'endpoint public
        renvoie 404 (lien mort). Idempotent. Écriture : responsable/admin."""
        partage = self.get_object()
        services.revoke_partage(partage)
        partage.refresh_from_db()
        return Response(
            PartageGedSerializer(partage, context={'request': request}).data)


class PolitiqueRetentionViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED22 — CRUD des politiques de rétention (scopé société).

    Une politique décrit la durée de conservation d'une classe de documents et
    l'action à l'échéance (DÉFAUT « signaler », purement consultatif). `company`
    et `created_by` sont posés côté serveur (jamais lus du corps de requête) ;
    `cabinet`/`folder` sont bornés à la société courante par le serializer.

    Lecture : tout rôle authentifié. Création/modification/suppression :
    responsable/admin. L'action `echus` LISTE les documents échus au regard de
    leur politique applicable — elle ne supprime ni ne modifie jamais rien.
    """
    queryset = PolitiqueRetention.objects.select_related(
        'company', 'cabinet', 'folder', 'created_by').all()
    serializer_class = PolitiqueRetentionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description', 'type_document']
    ordering_fields = ['nom', 'duree_conservation_jours', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['echus']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = selectors.politiques_retention_for_company(
            self.request.user.company).select_related(
            'company', 'cabinet', 'folder', 'created_by')
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false'):
            qs = qs.filter(actif=False)
        return qs

    def perform_create(self, serializer):
        # company + created_by posés côté serveur (jamais du corps).
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    @action(detail=False, methods=['get'], url_path='echus')
    def echus(self, request):
        """GED22 — Liste les documents ÉCHUS au regard de leur politique.

        `GET …/politiques-retention/echus/`. Pour chaque document de la société,
        applique la politique de rétention ACTIVE la plus spécifique et renvoie
        ceux dont l'âge dépasse la durée de conservation. Purement CONSULTATIF :
        ne supprime ni ne modifie aucun document. Borné à la société."""
        echus = selectors.documents_echus(request.user.company)
        data = [
            {
                'document': doc.id,
                'document_nom': doc.nom,
                'politique': pol.id,
                'politique_nom': pol.nom,
                'action_echeance': pol.action_echeance,
                'duree_conservation_jours': pol.duree_conservation_jours,
                'jours_depasses': depasses,
            }
            for doc, pol, depasses in echus
        ]
        return Response(data)


class ArchivageLegalViewSet(TenantMixin,
                            mixins.ListModelMixin,
                            mixins.RetrieveModelMixin,
                            mixins.CreateModelMixin,
                            viewsets.GenericViewSet):
    """GED23 — Archivages légaux (LECTURE + CRÉATION seulement, scopé société).

    Trace IMMUABLE (write-once) : ce ViewSet expose la LISTE/le DÉTAIL et permet
    de CRÉER un archivage — il n'y a volontairement NI `update`/`partial_update`
    NI `destroy` (un archivage légal ne se modifie ni ne se supprime jamais).
    À la création, `company`, `archive_par`, `version`, `hash_integrite` et le
    verrou objet sont posés CÔTÉ SERVEUR via `services.archiver_legalement`
    (jamais lus du corps ; on lit seulement `document` + `motif`/`retain_until`).

    Lecture : tout rôle authentifié. Création : responsable/admin.
    """
    queryset = ArchivageLegal.objects.select_related(
        'document', 'version', 'archive_par').all()
    serializer_class = ArchivageLegalSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['archive_le', 'id']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = selectors.archivages_legaux_for_company(
            self.request.user.company)
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        return qs

    def create(self, request, *args, **kwargs):
        """Crée un archivage légal pour un document de la société courante.

        Body : `{"document": <id>, "motif": "<str?>",
        "retain_until": "<YYYY-MM-DD?>"}`. Le document est borné à la société
        (404 cross-société). `company`/`archive_par`/`version`/hash/object-lock
        sont posés côté serveur (jamais lus du corps)."""
        document_id = request.data.get('document')
        if not document_id:
            return Response(
                {'document': 'Le document à archiver est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        # Borne à la société courante (jamais un document d'autrui).
        document = (Document.objects.filter(company=request.user.company)
                    .filter(pk=document_id).first())
        if document is None:
            return Response(
                {'document': 'Document inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        retain_until = None
        raw_retain = request.data.get('retain_until')
        if raw_retain not in (None, '', 'null'):
            from django.utils.dateparse import parse_date
            retain_until = parse_date(str(raw_retain))
            if retain_until is None:
                return Response(
                    {'retain_until': 'Date invalide (format attendu : '
                                     'AAAA-MM-JJ).'},
                    status=status.HTTP_400_BAD_REQUEST)
        try:
            archivage = services.archiver_legalement(
                document, user=request.user,
                motif=(request.data.get('motif') or '').strip(),
                retain_until=retain_until)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            ArchivageLegalSerializer(
                archivage, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='dossier-preuve')
    def dossier_preuve(self, request, pk=None):
        """XGED6 — Exporte le DOSSIER DE PREUVE JSON d'un archivage légal :
        hash au dépôt, tous les contrôles d'intégrité successifs, horodatages
        (aligné « validation et conservation » loi 43-20)."""
        archivage = self.get_object()  # borné à la société (TenantMixin)
        return Response(
            services.dossier_preuve_archivage(archivage),
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='verifier-integrite')
    def verifier_integrite(self, request):
        """XGED6 — Déclenche un contrôle d'intégrité IMMÉDIAT (hors sweep
        planifié) pour la société courante. Écriture : responsable/admin."""
        synthese = services.verifier_integrite_archives(request.user.company)
        return Response(synthese, status=status.HTTP_200_OK)


class LegalHoldViewSet(TenantMixin,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.CreateModelMixin,
                       viewsets.GenericViewSet):
    """GED24 — Rétentions légales / legal holds (lecture + pose/levée, scopé société).

    Expose la LISTE/le DÉTAIL des holds (actifs ET levés — l'historique est
    conservé) et permet d'en POSER un (création) ; il n'y a volontairement NI
    `update`/`partial_update` (un hold ne se modifie pas — on le pose puis on le
    lève), la levée passant par l'action dédiée `<id>/lever/` ou
    `documents/<id>/lever-legal-hold/`. À la création, `company` et `place_par`
    sont posés CÔTÉ SERVEUR via `services.placer_legal_hold` (jamais lus du
    corps ; on lit seulement `document` + `motif`). Pose IDEMPOTENTE (pas de
    doublon de hold actif).

    Lecture : tout rôle authentifié. Pose/levée : responsable/admin.
    """
    queryset = LegalHold.objects.select_related(
        'document', 'place_par', 'leve_par').all()
    serializer_class = LegalHoldSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_pose', 'id']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = selectors.legal_holds_for_company(self.request.user.company)
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false'):
            qs = qs.filter(actif=False)
        return qs

    def create(self, request, *args, **kwargs):
        """Pose un legal hold sur un document de la société courante.

        Body : `{"document": <id>, "motif": "<str?>"}`. Le document est borné à
        la société (404 cross-société). `company`/`place_par` sont posés côté
        serveur (jamais lus du corps). Pose IDEMPOTENTE (hold actif existant
        renvoyé tel quel)."""
        document_id = request.data.get('document')
        if not document_id:
            return Response(
                {'document': 'Le document à geler est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        document = (Document.objects.filter(company=request.user.company)
                    .filter(pk=document_id).first())
        if document is None:
            return Response(
                {'document': 'Document inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            hold = services.placer_legal_hold(
                document, user=request.user,
                motif=(request.data.get('motif') or '').strip())
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            LegalHoldSerializer(hold, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='lever')
    def lever(self, request, pk=None):
        """GED24 — Lève ce hold (et tout autre hold actif du même document).

        `POST …/legal-holds/<id>/lever/`. Délègue à `services.lever_legal_hold`
        (qui lève TOUS les holds actifs du document — trace serveur). Renvoie le
        nombre de holds levés. Idempotent. Écriture : responsable/admin."""
        hold = self.get_object()
        try:
            leves = services.lever_legal_hold(hold.document, user=request.user)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({'leves': leves}, status=status.HTTP_200_OK)


class ModeleDocumentViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED27 — Modèles de documents (fusion/mailing → PDF WeasyPrint, scopé société).

    CRUD complet d'un `ModeleDocument` (corps HTML avec jetons ``{{ champ }}``) +
    deux actions de fusion :
      * `rendre`  — fusionne le modèle avec un `contexte` fourni et RENVOIE le PDF
        (téléchargement direct), sans rien stocker ;
      * `generer` — fusionne, rend le PDF et le DÉPOSE comme document GED (réutilise
        `services.deposit_document`).

    Couche GÉNÉRIQUE de documents INTERNES (attestations, courriers, mailing) —
    SÉPARÉE et DISTINCTE du chemin `/proposal` (rule #4), qui reste l'UNIQUE
    chemin des PDF de DEVIS client. La société est posée CÔTÉ SERVEUR (TenantMixin)
    — jamais lue du corps. Lecture : tout rôle authentifié ; écriture/rendu :
    responsable/admin."""
    queryset = ModeleDocument.objects.select_related(
        'company', 'created_by').all()
    serializer_class = ModeleDocumentSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'description', 'categorie']
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('1', 'true'):
            qs = qs.filter(actif=True)
        elif actif in ('0', 'false'):
            qs = qs.filter(actif=False)
        return qs

    def perform_create(self, serializer):
        # company + created_by posés côté serveur (jamais du corps).
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def _contexte_from_request(self, request):
        """Extrait le dictionnaire de fusion du corps de requête (`contexte`).

        Accepte `{"contexte": {...}}`. Garde stricte : le contexte doit être un
        objet (dict) — tout autre type est rejeté (400)."""
        contexte = request.data.get('contexte', {})
        if contexte in (None, ''):
            return {}
        if not isinstance(contexte, dict):
            raise ValueError(
                "Le champ « contexte » doit être un objet de données de fusion.")
        return contexte

    @action(detail=True, methods=['post'], url_path='rendre')
    def rendre(self, request, pk=None):
        """GED27 — Fusionne ce modèle avec un `contexte` et renvoie le PDF.

        `POST …/modeles-document/<id>/rendre/` body `{"contexte": {...}}`.
        Substitution SÛRE (moteur de gabarit Django, contexte borné, jamais
        d'exécution de code) puis rendu WeasyPrint. Le PDF est renvoyé en
        téléchargement direct — rien n'est stocké. Écriture : responsable/admin."""
        modele = self.get_object()  # borné à la société (TenantMixin)
        try:
            contexte = self._contexte_from_request(request)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pdf_bytes = services.rendre_modele(modele, contexte)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        safe_name = (modele.nom or 'document').replace('"', '')
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{safe_name}.pdf"'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp

    @action(detail=True, methods=['post'], url_path='generer')
    def generer(self, request, pk=None):
        """GED27 + GED28 — Fusionne, rend le PDF et le DÉPOSE/CLASSE en GED.

        `POST …/modeles-document/<id>/generer/` body `{"contexte": {...}}`.
        Réutilise `services.generer_document` (dépôt via `deposit_document`,
        idempotent par modèle). GED28 : le document est CLASSÉ automatiquement
        dans le cabinet/dossier résolu depuis la règle du modèle
        (`cabinet_cible`/`dossier_cible`, ce dernier templaté par le contexte) —
        cabinet/dossier auto-créés si absents ; à défaut de cible, le dossier
        par défaut historique. `company`/`created_by` posés côté serveur. Renvoie
        l'id du document GED créé. Écriture : responsable/admin."""
        modele = self.get_object()  # borné à la société (TenantMixin)
        try:
            contexte = self._contexte_from_request(request)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            document, created = services.generer_document(
                modele, contexte,
                company=request.user.company,
                created_by=request.user)
        except RuntimeError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'document': document.id, 'document_nom': document.nom,
             'created': created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class DemandeSignatureDocumentViewSet(TenantMixin,
                                      mixins.ListModelMixin,
                                      mixins.RetrieveModelMixin,
                                      mixins.CreateModelMixin,
                                      viewsets.GenericViewSet):
    """GED30 — Demandes de signature électronique (point d'intégration + stub no-op).

    Expose la LISTE/le DÉTAIL des demandes et permet d'en CRÉER une (création) ;
    il n'y a volontairement NI `update`/`partial_update`/`destroy` (l'état évolue
    via le service / l'action `marquer-signe`, jamais par mutation directe). À la
    création, `company` et `created_by` sont posés CÔTÉ SERVEUR via
    `services.demander_signature` (jamais lus du corps ; on lit seulement
    `document`, `signataire_nom`, `signataire_email`). Le document est borné à la
    société (404 cross-société).

    KEY-GATED no-op : sans provider e-sign configuré (`services.esign_active()`
    faux), la demande est un STUB purement local `en_attente` — aucun appel
    réseau, aucun coût, aucune dépendance nouvelle. La complétion (webhook/manuel)
    passe par l'action `<id>/marquer-signe/`. Couche distincte de la signature des
    contrats (CONTRAT16) et du funnel `STAGES.py`.

    Lecture : tout rôle authentifié. Création / marquage : responsable/admin."""
    queryset = DemandeSignatureDocument.objects.select_related(
        'document', 'created_by').all()
    serializer_class = DemandeSignatureDocumentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date_demande', 'id']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = selectors.demandes_signature_for_company(self.request.user.company)
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        """Crée une demande de signature sur un document de la société courante.

        Body : `{"document": <id>, "signataire_nom": "<str>",
        "signataire_email": "<email>"}`. Le document est borné à la société (404
        cross-société). `company`/`created_by` posés côté serveur (jamais lus du
        corps). Mode STUB no-op tant qu'aucun provider e-sign n'est configuré."""
        document_id = request.data.get('document')
        nom = (request.data.get('signataire_nom') or '').strip()
        email = (request.data.get('signataire_email') or '').strip()
        if not document_id:
            return Response(
                {'document': 'Le document à signer est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        if not nom or not email:
            return Response(
                {'signataire': 'Le nom et l\'email du signataire sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        document = (Document.objects.filter(company=request.user.company)
                    .filter(pk=document_id).first())
        if document is None:
            return Response(
                {'document': 'Document inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        # XGED18 — un document-lien (URL externe) refuse la signature.
        try:
            services.assert_not_document_lien(document, action='signature')
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            demande = services.demander_signature(
                document,
                signataire_nom=nom,
                signataire_email=email,
                company=request.user.company,
                created_by=request.user)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            DemandeSignatureDocumentSerializer(
                demande, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='marquer-signe')
    def marquer_signe(self, request, pk=None):
        """GED30 — Enregistre la COMPLÉTION d'une signature (webhook/manuel).

        `POST …/demandes-signature/<id>/marquer-signe/`. Bascule la demande en
        `signe` et horodate `date_signature` via `services.marquer_signe`. Un
        `provider_ref` optionnel (callback) est conservé. Idempotent. Écriture :
        responsable/admin."""
        demande = self.get_object()  # borné à la société (TenantMixin)
        demande = services.marquer_signe(
            demande,
            provider_ref=(request.data.get('provider_ref') or '').strip())
        return Response(
            DemandeSignatureDocumentSerializer(
                demande, context={'request': request}).data,
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='prolonger')
    def prolonger(self, request, pk=None):
        """ZGED14 — Prolonge l'échéance d'une demande `en_attente` (versant
        ÉMETTEUR des relances). Body : `{"expires_at": "<iso>"}`. Réarme la
        notification d'expiration proche (le prochain sweep peut re-notifier
        sur la nouvelle échéance)."""
        demande = self.get_object()
        raw = request.data.get('expires_at')
        if not raw:
            return Response(
                {'expires_at': 'La nouvelle échéance est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        from django.utils.dateparse import parse_datetime

        expires_at = parse_datetime(raw)
        if expires_at is None:
            return Response(
                {'expires_at': 'Date invalide (format ISO attendu).'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            demande = services.prolonger_demande_signature(
                demande, expires_at=expires_at, user=request.user)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            DemandeSignatureDocumentSerializer(
                demande, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='creer-multi')
    def creer_multi(self, request):
        """XGED2 — Crée une demande de signature MULTI-destinataires.

        Body : `{"document": <id>, "destinataires": [{"nom", "email"?,
        "telephone"?, "role"?, "ordre"?}, …], "routage"?: "sequentiel"|
        "parallele", "expires_at"?: <iso>, "relance_cadence_jours"?: <int>}`.
        Le document est borné à la société (404 cross-société).
        `company`/`created_by` posés côté serveur."""
        document_id = request.data.get('document')
        destinataires = request.data.get('destinataires') or []
        if not document_id:
            return Response(
                {'document': 'Le document à signer est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        if not destinataires:
            return Response(
                {'destinataires': 'Au moins un destinataire est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        document = (Document.objects.filter(company=request.user.company)
                    .filter(pk=document_id).first())
        if document is None:
            return Response(
                {'document': 'Document inconnu.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            demande = services.creer_demande_multi_signataires(
                document, destinataires=destinataires,
                company=request.user.company,
                routage=request.data.get('routage'),
                expires_at=request.data.get('expires_at'),
                relance_cadence_jours=request.data.get('relance_cadence_jours'),
                created_by=request.user)
        except (PermissionError, ValueError) as exc:
            code = (status.HTTP_403_FORBIDDEN
                    if isinstance(exc, PermissionError)
                    else status.HTTP_400_BAD_REQUEST)
            return Response({'detail': str(exc)}, status=code)
        return Response(
            DemandeSignatureDocumentSerializer(
                demande, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """XGED2 — Annule une demande de signature (action ÉMETTEUR, tracée).

        `POST …/demandes-signature/<id>/annuler/`. Une demande déjà `signe`/
        `refuse` ne peut plus être annulée (400). Écriture : responsable/admin."""
        demande = self.get_object()  # borné à la société (TenantMixin)
        try:
            demande = services.annuler_demande(demande, user=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DemandeSignatureDocumentSerializer(
                demande, context={'request': request}).data,
            status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='tableau-bord')
    def tableau_bord(self, request):
        """ZGED3 — Tableau de bord des demandes de signature (kanban par
        statut + suivi de progression).

        `GET …/demandes-signature/tableau-bord/?emetteur=<id>&
        date_debut=AAAA-MM-JJ&date_fin=AAAA-MM-JJ` — pour chaque statut, la
        liste des demandes avec document, signataires + leur statut
        individuel (XGED2), % de complétion, date d'envoi, échéance/
        expiration, dernier événement ; drill-down = l'id de la demande
        (`GET demandes-signature/<id>/`). Filtrable par émetteur/période.
        Gestion/admin uniquement (403 sinon)."""
        from django.utils.dateparse import parse_date

        emetteur = request.query_params.get('emetteur')
        data = selectors.tableau_bord_signatures(
            request.user.company,
            emetteur=int(emetteur) if emetteur else None,
            date_debut=parse_date(request.query_params.get('date_debut') or ''),
            date_fin=parse_date(request.query_params.get('date_fin') or ''))
        return Response(data)


class RoleSignataireViewSet(TenantMixin, viewsets.ModelViewSet):
    """ZGED1 — Catalogue de rôles signataires réutilisables (couleur + auth
    extra + peut changer de signataire).

    CRUD scopé société ; `company`/`created_by` posés côté serveur. Lecture :
    tout rôle authentifié. Écriture : responsable/admin."""
    queryset = RoleSignataire.objects.select_related('created_by').all()
    serializer_class = RoleSignataireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nom', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class SignataireDemandeViewSet(TenantMixin, mixins.ListModelMixin,
                               mixins.RetrieveModelMixin,
                               viewsets.GenericViewSet):
    """XGED2 — Destinataires d'une demande de signature (LECTURE SEULE via
    l'API authentifiée). Créés/mutés uniquement via `services` (création
    groupée, cérémonie publique par jeton, notifications/relances)."""
    queryset = SignataireDemande.objects.select_related(
        'demande', 'role_signataire').all()
    serializer_class = SignataireDemandeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'id']
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        qs = SignataireDemande.objects.filter(
            company=self.request.user.company).select_related(
            'demande', 'role_signataire')
        demande = self.request.query_params.get('demande')
        if demande:
            qs = qs.filter(demande_id=demande)
        return qs


class ChampSignatureViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED3 — Zones de champs positionnées (placement de modèle de signature).

    `company` posée CÔTÉ SERVEUR (`TenantMixin.perform_create`) — jamais lue
    du corps. Lecture : tout rôle authentifié. Écriture (placement/édition/
    suppression) : responsable/admin. La page publique de cérémonie
    (XGED1/XGED3 `public_signature`) expose ces champs en LECTURE via son
    propre payload — jamais par cette route authentifiée."""
    queryset = ChampSignature.objects.select_related('demande', 'modele').all()
    serializer_class = ChampSignatureSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['page', 'y', 'x', 'id']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = ChampSignature.objects.filter(
            company=self.request.user.company).select_related(
                'demande', 'modele', 'type_champ_ref')
        demande = self.request.query_params.get('demande')
        if demande:
            qs = qs.filter(demande_id=demande)
        modele = self.request.query_params.get('modele')
        if modele:
            qs = qs.filter(modele_id=modele)
        return qs


class TypeChampSignatureViewSet(TenantMixin, viewsets.ModelViewSet):
    """ZGED4 — Catalogue de types de champs de signature personnalisés.

    CRUD scopé société ; `company`/`created_by` posés côté serveur. Lecture :
    tout rôle authentifié. Écriture : responsable/admin. Les 5 types de base
    sont seedés par `manage.py seed_types_champ_signature` (idempotent) —
    jamais recréés par cette API."""
    queryset = TypeChampSignature.objects.select_related('created_by').all()
    serializer_class = TypeChampSignatureSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['libelle', 'code', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() in ('1', 'true', 'yes'))
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class RoutageDocumentaireViewSet(TenantMixin, viewsets.ModelViewSet):
    """ZGED6 — Réglages de centralisation des fichiers d'un autre module vers
    un dossier GED. CRUD scopé société ; `company`/`created_by` posés côté
    serveur. Lecture : tout rôle authentifié. Écriture : responsable/admin."""
    queryset = RoutageDocumentaire.objects.select_related(
        'cabinet_cible', 'created_by').prefetch_related('tags_defaut').all()
    serializer_class = RoutageDocumentaireSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['source', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class VueGedEnregistreeViewSet(TenantMixin, viewsets.ModelViewSet):
    """ZGED8 — Recherches/filtres GED enregistrés et partageables.

    Lecture : chacun voit ses vues PRIVÉES + les vues PARTAGÉES de sa société
    (jamais les vues privées d'un collègue). Écriture (création/édition) :
    tout rôle authentifié, `utilisateur` posé côté serveur. Suppression :
    réservée au créateur OU à un gestionnaire/admin."""
    queryset = VueGedEnregistree.objects.select_related('utilisateur').all()
    serializer_class = VueGedEnregistreeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['nom', 'created_at']
    permission_classes = [IsAnyRole]

    def get_queryset(self):
        company = self.request.user.company
        return VueGedEnregistree.objects.filter(company=company).filter(
            models.Q(utilisateur=self.request.user) | models.Q(partagee=True)
        ).select_related('utilisateur')

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, utilisateur=self.request.user)

    def perform_destroy(self, instance):
        is_owner = instance.utilisateur_id == self.request.user.id
        is_manager = IsResponsableOrAdmin().has_permission(self.request, self)
        if not (is_owner or is_manager):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                "Seul le créateur ou un gestionnaire peut supprimer cette vue.")
        instance.delete()


class JournalAccesViewSet(TenantMixin, mixins.ListModelMixin,
                          mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GED35 — Journal d'audit d'accès aux documents (LECTURE SEULE).

    Append-only : aucune création/modification/suppression via l'API (les
    entrées sont posées côté serveur par `services.journaliser_acces` au moment
    d'une lecture). Tout est borné à la société (TenantMixin). Filtrable par
    `?document=<id>`, `?utilisateur=<id>`, `?type_acces=<code>`. Lecture réservée
    aux responsables/admins (l'audit est sensible)."""
    queryset = JournalAcces.objects.select_related(
        'document', 'utilisateur').all()
    serializer_class = JournalAccesSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'type_acces']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        company = self.request.user.company
        qs = selectors.journal_acces_for_company(
            company,
            document=None,
            type_acces=self.request.query_params.get('type_acces') or None)
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        utilisateur = self.request.query_params.get('utilisateur')
        if utilisateur:
            qs = qs.filter(utilisateur_id=utilisateur)
        return qs


class QuotaStockageViewSet(TenantMixin, viewsets.ModelViewSet):
    """GED36 — Quota de stockage de la société (consultation + réglage admin).

    Au plus UNE entrée par société (OneToOne). `company` posée CÔTÉ SERVEUR
    (jamais lue du corps). Lecture : tout rôle authentifié (voir l'usage/quota) ;
    écriture (fixer le quota) : responsable/admin. Expose `usage`/`quota`/
    `restant` via l'action `etat` (toujours disponible, même sans entrée)."""
    queryset = QuotaStockage.objects.select_related('company').all()
    serializer_class = QuotaStockageSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'etat':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(
            company=self.request.user.company)

    def perform_create(self, serializer):
        # OneToOne : on ne crée jamais un second quota pour la société. Si une
        # entrée existe déjà, on met à jour la sienne (idempotent côté société).
        company = self.request.user.company
        existant = QuotaStockage.objects.filter(company=company).first()
        if existant is not None:
            existant.quota_octets = serializer.validated_data.get(
                'quota_octets', existant.quota_octets)
            existant.save(update_fields=['quota_octets', 'updated_at'])
            serializer.instance = existant
            return
        serializer.save(company=company)

    @action(detail=False, methods=['get'], url_path='etat')
    def etat(self, request):
        """GED36 — État du stockage de la société : usage / quota / restant.

        `GET …/quotas-stockage/etat/`. Toujours disponible (même sans entrée
        `QuotaStockage` explicite : le défaut `GED_QUOTA_DEFAUT_OCTETS`
        s'applique). Renvoie `{usage_octets, quota_octets, restant_octets,
        depasse, illimite}`."""
        company = request.user.company
        usage = services.usage_stockage_octets(company)
        quota = services.quota_octets(company)
        return Response({
            'usage_octets': usage,
            'quota_octets': quota,
            'restant_octets': services.quota_restant_octets(company),
            'depasse': services.quota_depasse(company),
            'illimite': quota <= 0,
        })


class DepotPublicViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED7 — Gestion (côté propriétaire) des liens de dépôt public.

    `company`/`created_by`/`token` posés côté serveur. L'accès public au dépôt
    passe par l'endpoint token-only `public_depot` (AllowAny), jamais par ce
    viewset. Lecture : tout rôle. Création/révocation : responsable/admin."""
    queryset = DepotPublic.objects.select_related('folder', 'created_by').all()
    serializer_class = DepotPublicSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'expires_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        folder = self.request.query_params.get('folder')
        if folder:
            qs = qs.filter(folder_id=folder)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='revoquer')
    def revoquer(self, request, pk=None):
        """XGED7 — Révoque ce lien de dépôt (kill-switch). Écriture :
        responsable/admin."""
        depot = self.get_object()
        services.revoke_depot_public(depot)
        depot.refresh_from_db()
        return Response(
            DepotPublicSerializer(depot, context={'request': request}).data)


class ExigenceDossierViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED8 — Modèle de checklist de pièces requises (par société)."""
    queryset = ExigenceDossier.objects.select_related('cabinet', 'folder').all()
    serializer_class = ExigenceDossierSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['libelle', 'description']
    ordering_fields = ['libelle', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class DemandeDocumentViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED8 — Demandes de pièces (placeholder + relances jusqu'au dépôt)."""
    queryset = DemandeDocument.objects.select_related(
        'folder', 'exigence', 'utilisateur', 'document').all()
    serializer_class = DemandeDocumentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'echeance']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        folder = self.request.query_params.get('folder')
        if folder:
            qs = qs.filter(folder_id=folder)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        folder = serializer.validated_data['folder']
        instance = services.creer_demande_document(
            folder=folder, company=self.request.user.company,
            libelle=serializer.validated_data['libelle'],
            created_by=self.request.user,
            exigence=serializer.validated_data.get('exigence'),
            utilisateur=serializer.validated_data.get('utilisateur'),
            destinataire_nom=serializer.validated_data.get('destinataire_nom', ''),
            destinataire_email=serializer.validated_data.get(
                'destinataire_email', ''),
            echeance=serializer.validated_data.get('echeance'))
        serializer.instance = instance

    @action(detail=True, methods=['post'], url_path='relancer')
    def relancer(self, request, pk=None):
        """XGED8 — Relance manuelle immédiate de cette demande."""
        demande = self.get_object()
        services.relancer_demande_document(demande)
        demande.refresh_from_db()
        return Response(
            DemandeDocumentSerializer(demande, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='checklist')
    def checklist(self, request):
        """XGED8 — Checklist requis/présent/manquant d'un dossier.

        `GET …/demandes-document/checklist/?folder=<id>`."""
        folder_id = request.query_params.get('folder')
        if not folder_id:
            return Response(
                {'folder': 'Le dossier est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        folder = Folder.objects.filter(
            company=request.user.company, pk=folder_id).first()
        if folder is None:
            return Response(
                {'folder': 'Dossier inconnu.'}, status=status.HTTP_404_NOT_FOUND)
        resultat = services.checklist_dossier(folder)
        data = [{
            'exigence': ExigenceDossierSerializer(
                item['exigence'], context={'request': request}).data,
            'statut': item['statut'],
            'demande': (DemandeDocumentSerializer(
                item['demande'], context={'request': request}).data
                if item['demande'] else None),
        } for item in resultat]
        return Response(data)


class ValidationOcrDocumentViewSet(TenantMixin, mixins.ListModelMixin,
                                   mixins.RetrieveModelMixin,
                                   viewsets.GenericViewSet):
    """XGED13 — File de validation d'extraction OCR (score de confiance).

    CRUD : lecture seule (list/retrieve) ; la décision passe par l'action
    `valider` (jamais un PATCH brut sur `champs_extraits`)."""
    queryset = ValidationOcrDocument.objects.select_related(
        'document', 'valide_par').all()
    serializer_class = ValidationOcrDocumentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'score_confiance']

    def get_permissions(self):
        return [IsAnyRole()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        en_attente = self.request.query_params.get('en_attente')
        if en_attente in ('1', 'true'):
            qs = qs.filter(valide=False)
        return qs

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """XGED13 — Valide (avec corrections) cette extraction en attente.

        Corps optionnel : `{"champs_corriges": {...}}` (sinon les champs
        proposés sont appliqués tels quels)."""
        validation = self.get_object()
        champs = request.data.get('champs_corriges')
        if champs is None:
            champs = validation.champs_extraits
        resultat = services.valider_extraction_ocr(
            validation, champs_corriges=champs, user=request.user)
        return Response(
            ValidationOcrDocumentSerializer(
                resultat, context={'request': request}).data)


class AnnotationDocumentViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED16 — Annotations/tampons sur l'image d'une version (couche séparée
    — le fichier original n'est jamais modifié)."""
    queryset = AnnotationDocument.objects.select_related('version', 'auteur').all()
    serializer_class = AnnotationDocumentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['page', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS or self.action == 'tampons':
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        version = self.request.query_params.get('version')
        if version:
            qs = qs.filter(version_id=version)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, auteur=self.request.user)

    @action(detail=False, methods=['get'], url_path='tampons')
    def tampons(self, request):
        """XGED16 — Tampons disponibles pour la société (système + propres)."""
        return Response(services.tampons_disponibles(request.user.company))

    @action(detail=False, methods=['get'], url_path='export-annote')
    def export_annote(self, request):
        """XGED16 — Exporte un PDF annoté APLATI (nouveau fichier séparé).

        `GET …/annotations/export-annote/?version=<id>`. Sans PyMuPDF : 400
        explicite."""
        version_id = request.query_params.get('version')
        version = DocumentVersion.objects.filter(
            company=request.user.company, pk=version_id).first()
        if version is None:
            return Response(
                {'version': 'Version inconnue.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            out_bytes = services.exporter_pdf_annote(version)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        response = HttpResponse(out_bytes, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{version.filename or "annote"}-annote.pdf"')
        return response


class RegleDossierViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED19 — Règles d'action automatique à l'upload dans un dossier."""
    queryset = RegleDossier.objects.select_related('folder', 'created_by').all()
    serializer_class = RegleDossierSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['ordre', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        folder = self.request.query_params.get('folder')
        if folder:
            qs = qs.filter(folder_id=folder)
        return qs

    def perform_create(self, serializer):
        from core.rules import validate_condition_group
        errors = validate_condition_group(
            serializer.validated_data.get('condition_group') or {})
        if errors:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'condition_group': errors})
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class RegleApprobationGedViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED20 — Routage conditionnel des approbations par métadonnées."""
    queryset = RegleApprobationGed.objects.select_related('created_by').all()
    serializer_class = RegleApprobationGedSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['priorite', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    def perform_create(self, serializer):
        from core.rules import validate_condition_group
        errors = validate_condition_group(
            serializer.validated_data.get('condition_group') or {})
        if errors:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'condition_group': errors})
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class RegleAclMetadonneeViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED21 — ACL automatiques pilotées par métadonnées (couche dynamique).

    CRUD des règles ; l'admin voit toujours tout (résolution `acl_effective`
    inconditionnelle pour lui). Lecture : tout rôle authentifié. Écriture :
    responsable/admin."""
    queryset = RegleAclMetadonnee.objects.select_related(
        'role', 'created_by').all()
    serializer_class = RegleAclMetadonneeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['priorite', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return selectors.regles_acl_metadonnee_for_company(
            self.request.user.company)

    def perform_create(self, serializer):
        from core.rules import validate_condition_group
        errors = validate_condition_group(
            serializer.validated_data.get('condition_group') or {})
        if errors:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'condition_group': errors})
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


class DemandeDispositionViewSet(TenantMixin,
                                mixins.ListModelMixin,
                                mixins.RetrieveModelMixin,
                                mixins.CreateModelMixin,
                                viewsets.GenericViewSet):
    """XGED23 — Workflow de disposition fin de rétention (revue + certificat).

    Lecture + création (proposition d'un lot). La décision passe par les
    actions dédiées `approuver`/`rejeter`, l'exécution par `executer` (jamais
    un PATCH brut du statut). Lecture : tout rôle authentifié. Écriture :
    responsable/admin."""
    queryset = DemandeDisposition.objects.select_related(
        'demandeur', 'approbateur').prefetch_related('certificats').all()
    serializer_class = DemandeDispositionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'statut']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        """Propose un lot de disposition à partir d'ids de documents.

        Body : `{"libelle": "<str>", "action": "detruire|archiver",
        "documents": [<id>, …]}`. Les holds actifs (GED24) sont exclus
        d'office ; `company`/`demandeur` posés côté serveur."""
        libelle = (request.data.get('libelle') or '').strip()
        action_disp = request.data.get('action') or 'detruire'
        document_ids = request.data.get('documents') or []
        if not libelle or not document_ids:
            return Response(
                {'detail': 'libelle et documents (liste) sont requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            demande = services.creer_demande_disposition(
                request.user.company, libelle=libelle,
                document_ids=document_ids, action=action_disp,
                user=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DemandeDispositionSerializer(
                demande, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='approuver')
    def approuver(self, request, pk=None):
        """XGED23 — Approuve cette demande (ne détruit pas encore).

        Corps optionnel `{"commentaire": "<str?>"}`. Écriture : responsable/
        admin."""
        demande = self.get_object()
        try:
            demande = services.approuver_demande_disposition(
                demande, user=request.user,
                commentaire=(request.data.get('commentaire') or '').strip())
        except DemandeDispositionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            DemandeDispositionSerializer(
                demande, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='rejeter')
    def rejeter(self, request, pk=None):
        """XGED23 — Rejette cette demande : CONSERVE tous les documents du lot.

        Corps optionnel `{"commentaire": "<str?>"}`. Écriture : responsable/
        admin."""
        demande = self.get_object()
        try:
            demande = services.rejeter_demande_disposition(
                demande, user=request.user,
                commentaire=(request.data.get('commentaire') or '').strip())
        except DemandeDispositionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            DemandeDispositionSerializer(
                demande, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='executer')
    def executer(self, request, pk=None):
        """XGED23 — Exécute une demande APPROUVÉE : détruit (ou archive) le
        lot et émet un `CertificatDestruction` par document réellement
        détruit. Écriture : responsable/admin."""
        demande = self.get_object()
        try:
            services.executer_demande_disposition(demande, user=request.user)
        except DemandeDispositionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        demande.refresh_from_db()
        return Response(
            DemandeDispositionSerializer(
                demande, context={'request': request}).data)


class LotEnvoiViewSet(TenantMixin,
                      mixins.ListModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """XGED27 — Lots d'envoi en masse de demandes de signature (lecture +
    action de création dédiée `envoi-masse`).

    Lecture : tout rôle authentifié. Création du lot (envoi en masse) :
    responsable/admin."""
    queryset = LotEnvoi.objects.select_related('modele', 'created_by').all()
    serializer_class = LotEnvoiSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)

    @action(detail=False, methods=['post'], url_path='envoi-masse',
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def envoi_masse(self, request):
        """XGED27 — Envoi en masse : un `ModeleDocument` + une liste de
        destinataires → un document personnalisé + une demande de signature
        PAR destinataire, suivis sous un `LotEnvoi`.

        Corps (multipart ou JSON) : `{"modele": <id>, "libelle": "<str?>"}`
        et SOIT un fichier `csv` (colonnes `nom`,`email`,+champs de fusion
        libres), SOIT `clients: [<id>, ...]` (résolus en lecture seule via
        `crm.selectors.client_base_qs` — jamais un import de `crm.models`).
        Les erreurs par ligne sont rapportées dans `resultats` sans bloquer
        le lot. Écriture : responsable/admin."""
        modele_id = request.data.get('modele')
        if not modele_id:
            return Response(
                {'modele': 'Le modèle de document est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        modele = ModeleDocument.objects.filter(
            company=request.user.company, pk=modele_id).first()
        if modele is None:
            return Response(
                {'modele': 'Modèle inconnu.'}, status=status.HTTP_404_NOT_FOUND)

        destinataires = []
        csv_file = request.FILES.get('csv')
        if csv_file is not None:
            try:
                csv_text = csv_file.read().decode('utf-8-sig')
            except Exception:
                return Response(
                    {'csv': 'CSV illisible (encodage attendu : UTF-8).'},
                    status=status.HTTP_400_BAD_REQUEST)
            destinataires = services.parser_csv_metadonnees(csv_text)
        else:
            client_ids = (request.data.getlist('clients')
                          if hasattr(request.data, 'getlist')
                          else request.data.get('clients')) or []
            if client_ids:
                from apps.crm import selectors as crm_selectors
                clients = crm_selectors.client_base_qs(
                    request.user.company).filter(pk__in=client_ids)
                for client in clients:
                    nom_complet = ' '.join(
                        p for p in [client.nom, getattr(client, 'prenom', '')]
                        if p).strip() or client.nom
                    destinataires.append({
                        'nom': nom_complet, 'email': client.email or '',
                    })
        if not destinataires:
            return Response(
                {'detail': 'Aucun destinataire : fournir un CSV ou une '
                           'sélection de clients.'},
                status=status.HTTP_400_BAD_REQUEST)

        lot = services.creer_lot_envoi_signature(
            company=request.user.company, modele=modele,
            destinataires=destinataires,
            libelle=(request.data.get('libelle') or '').strip(),
            created_by=request.user)
        return Response(
            LotEnvoiSerializer(lot, context={'request': request}).data,
            status=status.HTTP_201_CREATED)


class PlanificationDocumentViewSet(TenantMixin, viewsets.ModelViewSet):
    """XGED15 — Activités planifiées sur un document."""
    queryset = PlanificationDocument.objects.select_related(
        'document', 'assigne_a', 'created_by').all()
    serializer_class = PlanificationDocumentSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['echeance', 'created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset().filter(company=self.request.user.company)
        document = self.request.query_params.get('document')
        if document:
            qs = qs.filter(document_id=document)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)


@api_view(['GET'])
@permission_classes([IsAnyRole])
def mes_recents(request):
    """ZGED13 — Documents récemment consultés/déposés par l'APPELANT
    uniquement (jamais ceux d'un collègue).

    `GET ged/mes-recents/?limit=<n>` — dérivé de `JournalAcces` (GED35) et
    `DocumentVersion.uploaded_by`, dédupliqués par document, hors
    corbeille/ACL refusée. Renvoie `{"consultes": [...], "deposes": [...]}`."""
    try:
        limit = min(int(request.query_params.get('limit', 10)), 50)
    except (TypeError, ValueError):
        limit = 10
    consultes = selectors.mes_recents(request.user, limit=limit)
    deposes = selectors.mes_derniers_depots(request.user, limit=limit)
    return Response({
        'consultes': DocumentSerializer(
            consultes, many=True, context={'request': request}).data,
        'deposes': DocumentSerializer(
            deposes, many=True, context={'request': request}).data,
    })


@api_view(['GET'])
@permission_classes([IsAnyRole])
def mes_favoris(request):
    """ZGED7 — Dossiers et documents favoris de l'APPELANT uniquement.

    `GET ged/mes-favoris/` — jamais les favoris d'un collègue (personnel).
    Renvoie `{"dossiers": [...], "documents": [...]}`."""
    favoris = FavoriGed.objects.filter(
        company=request.user.company, utilisateur=request.user
    ).select_related('folder', 'document')
    dossiers = [
        {'id': f.folder.pk, 'nom': f.folder.nom, 'favori_id': f.pk}
        for f in favoris if f.folder_id
    ]
    documents = [
        {'id': f.document.pk, 'nom': f.document.nom, 'favori_id': f.pk}
        for f in favoris if f.document_id
    ]
    return Response({'dossiers': dossiers, 'documents': documents})


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def analytique_ged(request):
    """XGED26 — Analytique workflow d'approbation & signature (KPIs réels).

    `GET ged/analytique/?date_debut=AAAA-MM-JJ&date_fin=AAAA-MM-JJ` — responsable/
    admin uniquement. Renvoie `{"approbations": {...}, "signatures": {...}}`
    (voir `selectors.analytique_approbations`/`analytique_signatures` pour le
    détail des clés) sur des données RÉELLES de la société courante, période
    filtrable, divide-by-zero gardé (aucune donnée → moyennes `None`, jamais
    une 500)."""
    from django.utils.dateparse import parse_date

    date_debut = parse_date(request.query_params.get('date_debut') or '')
    date_fin = parse_date(request.query_params.get('date_fin') or '')
    company = request.user.company
    return Response({
        'approbations': selectors.analytique_approbations(
            company, date_debut=date_debut, date_fin=date_fin),
        'signatures': selectors.analytique_signatures(
            company, date_debut=date_debut, date_fin=date_fin),
    })


# ── GED20 — Endpoint PUBLIC (sans login) servant un document par jeton ───────
# AUTHENTIFIÉ UNIQUEMENT PAR LE JETON : aucune identité/société n'est lue de la
# requête. Tout est résolu DEPUIS le jeton (qui ne référence qu'un seul document
# d'une seule société). Révoqué/inconnu → 404 ; expiré/quota épuisé → 410 ;
# mot de passe manquant/erroné → 403. Aucune autre donnée n'est atteignable.

class PublicPartageRateThrottle(SimpleRateThrottle):
    """Limite le débit de l'accès public par IP + jeton (cache-based).

    Pas de dépendance externe : throttle DRF intégré + cache du projet. Décourage
    le balayage de jetons et l'aspiration de fichiers sans bloquer un accès
    légitime. Même motif que `ventes.public_views.PublicLinkRateThrottle`."""
    scope = 'public_ged_partage'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (getattr(view, 'kwargs', None) or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _ged_noindex(response):
    """Marque une réponse publique comme non-indexable par les moteurs."""
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PublicPartageRateThrottle])
def public_partage(request, token):
    """GED20 — Sert le document d'un partage tokenisé (PUBLIC, sans login).

    `GET /api/django/ged/public/<token>/[?password=…]` (ou en-tête
    `X-Partage-Password`). Le jeton est l'UNIQUE secret d'accès : aucune
    identité/société n'est lue de la requête. Le partage est résolu DEPUIS le
    jeton via `services.resolve_partage_public` (qui ne référence qu'un seul
    document d'une seule société — pas de fuite cross-locataire).

    Codes :
      - 404 : jeton inconnu OU partage révoqué (indistinct, pas de fuite).
      - 410 : partage expiré OU quota de téléchargements épuisé.
      - 403 : un mot de passe protège le partage et celui fourni est
        manquant/erroné (le `WWW-Authenticate`-like est implicite, message FR).
      - 200 : le contenu de la VERSION COURANTE du document est relayé
        même-origine (inline pour PDF/image/texte, attachment sinon) et le
        compteur `telechargements` est incrémenté atomiquement.

    Aucun prix d'achat ni document d'un autre locataire n'est jamais exposé.
    """
    password = (request.query_params.get('password')
                or request.META.get('HTTP_X_PARTAGE_PASSWORD')
                or '')
    statut, partage = services.resolve_partage_public(token, password=password)

    if statut == services.PARTAGE_INTROUVABLE:
        return _ged_noindex(Response(
            {'detail': "Ce lien de partage est introuvable ou a été révoqué."},
            status=status.HTTP_404_NOT_FOUND))
    if statut == services.PARTAGE_EXPIRE:
        return _ged_noindex(Response(
            {'detail': "Ce lien de partage a expiré ou n'est plus disponible."},
            status=status.HTTP_410_GONE))
    if statut == services.PARTAGE_MDP_REQUIS:
        return _ged_noindex(Response(
            {'detail': "Mot de passe requis ou incorrect pour ce document."},
            status=status.HTTP_403_FORBIDDEN))

    # statut == PARTAGE_OK — on sert le contenu de la version courante.
    version = selectors.latest_version(partage.document)
    if version is None:
        return _ged_noindex(Response(
            {'detail': "Aucun fichier disponible pour ce document."},
            status=status.HTTP_404_NOT_FOUND))

    # Consomme le quota AVANT de servir : un GET concurrent ne peut pas dépasser
    # `quota_max` (incrément atomique conditionnel). Si le quota vient d'être
    # épuisé par un autre accès, on renvoie 410 sans servir.
    if not services.consume_partage_download(partage):
        return _ged_noindex(Response(
            {'detail': "Ce lien de partage a expiré ou n'est plus disponible."},
            status=status.HTTP_410_GONE))

    data, err = fetch_attachment(version.file_key)
    if err:
        return _ged_noindex(Response(
            {'detail': "Document indisponible pour le moment."},
            status=status.HTTP_404_NOT_FOUND))

    mime = version.mime or 'application/octet-stream'
    safe_name = (version.filename or partage.document.nom
                 or 'document').replace('"', '')

    # GED21 — Contrôle de diffusion sur le lien PUBLIC : on filigrane le contenu
    # servi si CE partage est marqué (`partage.watermark`) OU si le document est
    # globalement marqué (`document.watermark_diffusion`). La société vient du
    # document (jamais de la requête publique). Best-effort : dégrade à
    # l'original si la lib manque ; flux byte-identique quand aucun drapeau n'est
    # posé. Aucun statut ni binaire stocké n'est modifié.
    if (getattr(partage, 'watermark', False)
            or getattr(partage.document, 'watermark_diffusion', False)):
        label = services.watermark_label(company=partage.document.company)
        data, marked = services.apply_watermark(data, mime, label)
        if marked and mime in services._WATERMARK_IMAGE_MIMES:
            mime = 'image/png'

    disposition = 'inline' if mime in _INLINE_MIMES else 'attachment'

    # GED35 — journalise l'accès PUBLIC (utilisateur anonyme, best-effort).
    from .models import ACCES_PUBLIC
    services.journaliser_acces(
        partage.document, utilisateur=None, type_acces=ACCES_PUBLIC,
        adresse_ip=services._adresse_ip_requete(request))

    resp = HttpResponse(data, content_type=mime)
    resp['Content-Disposition'] = f'{disposition}; filename="{safe_name}"'
    resp['X-Content-Type-Options'] = 'nosniff'
    return _ged_noindex(resp)


# ── XGED7 — Endpoint PUBLIC (sans login) de DÉPÔT par jeton ──────────────────
# Symétrique de GED20 (téléchargement) : un tiers UNIQUEMENT téléverse, ne voit
# JAMAIS le contenu existant du dossier. Authentifié uniquement par le jeton.

class PublicDepotRateThrottle(SimpleRateThrottle):
    """Limite le débit du dépôt public par IP + jeton (cache-based)."""
    scope = 'ged_public_depot'

    def get_cache_key(self, request, view):
        token = request.resolver_match.kwargs.get('token', '') if (
            request.resolver_match) else ''
        ident = f'{self.get_ident(request)}:{token}'
        return self.cache_format % {'scope': self.scope, 'ident': ident}


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicDepotRateThrottle])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def public_depot(request, token):
    """XGED7 — GET : infos du lien de dépôt (message d'instruction, quotas
    restants) ; POST : dépose un fichier. Jamais de visibilité sur le contenu
    déjà présent dans le dossier cible.

    Codes : 404 (jeton inconnu/révoqué) ; 410 (expiré ou quota épuisé) ; 400
    (fichier manquant/format refusé) ; 200/201 sinon."""
    statut, depot = services.resolve_depot_public(token)
    if statut == services.DEPOT_INTROUVABLE:
        return _ged_noindex(Response(
            {'detail': "Ce lien de dépôt est introuvable ou a été révoqué."},
            status=status.HTTP_404_NOT_FOUND))
    if statut == services.DEPOT_EXPIRE:
        return _ged_noindex(Response(
            {'detail': "Ce lien de dépôt a expiré ou n'accepte plus de fichiers."},
            status=status.HTTP_410_GONE))

    if request.method == 'GET':
        return _ged_noindex(Response({
            'message': depot.message,
            'quota_fichiers_restant': (
                None if depot.quota_fichiers is None
                else max(0, depot.quota_fichiers - depot.depots_effectues)),
        }))

    file = request.FILES.get('file')
    if not file:
        return _ged_noindex(Response(
            {'file': 'Aucun fichier fourni.'}, status=status.HTTP_400_BAD_REQUEST))
    meta, err = store_attachment(file)
    if err:
        return _ged_noindex(Response(
            {'file': err}, status=status.HTTP_400_BAD_REQUEST))
    try:
        document = services.deposer_via_lien_public(
            depot, file_key=meta['file_key'], filename=meta['filename'],
            size=meta['size'], mime=meta['mime'],
            uploader_nom=(request.data.get('nom') or '').strip(),
            uploader_email=(request.data.get('email') or '').strip())
    except ValueError as exc:
        return _ged_noindex(Response(
            {'detail': str(exc)}, status=status.HTTP_410_GONE))
    return _ged_noindex(Response(
        {'detail': 'Fichier déposé avec succès.', 'document': document.pk},
        status=status.HTTP_201_CREATED))


class PublicSignatureRateThrottle(SimpleRateThrottle):
    """XGED1 — Limite de débit de la cérémonie publique par IP + jeton.

    Même motif que `PublicPartageRateThrottle` (GED20) : décourage le balayage
    de jetons sans bloquer un signataire légitime."""
    scope = 'public_ged_signature'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (getattr(view, 'kwargs', None) or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': f'{ident}:{token}',
        }


def _signature_publique_payload(demande):
    """XGED1/XGED3 — Représentation JSON publique d'une demande (jamais de
    données d'une autre société ; aucun prix d'achat/marge — cette demande ne
    porte aucune donnée commerciale de toute façon). Inclut les champs
    positionnés (XGED3) — liste vide pour une demande sans champ (mono-champ
    rétrocompatible XGED1)."""
    document = demande.document
    return {
        'document_nom': document.nom,
        'document_id': document.id,
        'signataire_nom': demande.signataire_nom,
        'statut': demande.statut,
        'expires_at': demande.expires_at,
        'champs': ChampSignatureSerializer(demande.champs.all(), many=True).data,
    }


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicSignatureRateThrottle])
def public_signature(request, token):
    """XGED1 — Cérémonie de signature PUBLIQUE (sans login), loi 53-05.

    `GET /api/django/ged/signature/<token>/` : consulte la demande + le
    document à signer (réutilise le stream d'aperçu GED14 via `versions/<id>/
    apercu/` côté client, ce endpoint ne renvoie que les métadonnées).
    `POST /api/django/ged/signature/<token>/` avec
    `{"action": "signer", "consentement": true,
    "signature_texte"?: str, "signature_tracee"?: str}` ou
    `{"action": "refuser", "motif": str}`.

    Codes :
      - 404 : jeton inconnu (jamais de fuite).
      - 410 : demande expirée/annulée OU déjà traitée (signée/refusée) —
        idempotence visible, pas de re-signature.
      - 400 : consentement/signature manquants (signer) ou motif vide (refuser).
      - 200 : succès (GET consultation, ou POST signer/refuser).

    Ne touche NI `contrats.SignatureContrat` NI `/proposal` (rule #4)."""
    statut, demande = services.resolve_signature_publique(token)

    if statut == services.SIGNATURE_PUBLIQUE_INTROUVABLE:
        return _ged_noindex(Response(
            {'detail': "Ce lien de signature est introuvable."},
            status=status.HTTP_404_NOT_FOUND))
    if statut == services.SIGNATURE_PUBLIQUE_EXPIREE:
        return _ged_noindex(Response(
            {'detail': "Ce lien de signature a expiré ou a été annulé."},
            status=status.HTTP_410_GONE))
    if statut == services.SIGNATURE_PUBLIQUE_DEJA_TRAITEE:
        return _ged_noindex(Response(
            {'detail': "Cette demande a déjà été traitée (signée ou refusée).",
             'statut': demande.statut},
            status=status.HTTP_410_GONE))

    if request.method == 'GET':
        return _ged_noindex(
            Response(_signature_publique_payload(demande),
                     status=status.HTTP_200_OK))

    # POST — signer ou refuser.
    action_demandee = (request.data.get('action') or '').strip().lower()
    ip = services._adresse_ip_requete(request)
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:512]

    if action_demandee == 'refuser':
        try:
            demande = services.refuser_demande_publique(
                demande, motif=request.data.get('motif'),
                adresse_ip=ip, user_agent=ua)
        except ValueError as exc:
            return _ged_noindex(Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))
        return _ged_noindex(
            Response(_signature_publique_payload(demande),
                     status=status.HTTP_200_OK))

    if action_demandee == 'signer':
        try:
            # XGED3 — la variante champs-aware exige les champs `requis`
            # remplis puis délègue à `signer_demande_publique` (preuves
            # inchangées) ; comportement STRICTEMENT identique à XGED1 pour
            # une demande sans aucun `ChampSignature` (rétrocompatible).
            demande = services.signer_demande_publique_avec_champs(
                demande,
                consentement=bool(request.data.get('consentement')),
                signature_texte=request.data.get('signature_texte', ''),
                signature_tracee=request.data.get('signature_tracee', ''),
                adresse_ip=ip, user_agent=ua,
                valeurs_champs=request.data.get('valeurs_champs'))
        except ValueError as exc:
            return _ged_noindex(Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))
        return _ged_noindex(
            Response(_signature_publique_payload(demande),
                     status=status.HTTP_200_OK))

    return _ged_noindex(Response(
        {'detail': "Action inconnue : 'signer' ou 'refuser' attendu."},
        status=status.HTTP_400_BAD_REQUEST))


class PublicSignataireRateThrottle(PublicSignatureRateThrottle):
    """XGED2 — Même limite de débit que la cérémonie mono-partie, sur le
    jeton PROPRE à un destinataire du circuit multi-signataires."""
    scope = 'public_ged_signataire'


def _signataire_publique_payload(signataire):
    """XGED2 — Représentation JSON publique d'un destinataire (jamais de
    données d'une autre société ; ne révèle jamais les AUTRES destinataires).

    ZGED2 — expose `auth_extra`/`otp_requis` (jamais le code ni son hash) pour
    que l'écran public sache s'il doit demander un code avant de débloquer la
    signature."""
    demande = signataire.demande
    return {
        'document_nom': demande.document.nom,
        'document_id': demande.document_id,
        'nom': signataire.nom,
        'role': signataire.role,
        'ordre': signataire.ordre,
        'statut': signataire.statut,
        'demande_statut': demande.statut,
        'auth_extra': signataire.auth_extra_effective,
        'otp_requis': signataire.otp_requis_et_non_valide,
    }


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([PublicSignataireRateThrottle])
def public_signataire(request, token):
    """XGED2 — Cérémonie de signature PUBLIQUE d'UN destinataire du circuit
    multi-signataires (`SignataireDemande.token`), distincte du jeton de la
    demande globale (XGED1 `public_signature`, toujours servable pour le
    mono-signataire rétrocompatible).

    `GET /api/django/ged/signataire/<token>/` consulte ; `POST` avec
    `{"action": "signer"|"refuser", …}` (mêmes champs que `public_signature`).
    Un signataire qui n'est PAS encore `notifie` (séquentiel, pas son tour) ne
    peut ni signer ni refuser (403 explicite, jamais un blocage silencieux)."""
    signataire = (SignataireDemande.objects
                  .select_related(
                      'demande', 'demande__document', 'demande__document__company')
                  .filter(token=token)
                  .first())
    if signataire is None:
        return _ged_noindex(Response(
            {'detail': "Ce lien de signature est introuvable."},
            status=status.HTTP_404_NOT_FOUND))
    demande = signataire.demande
    from .models import (
        SIGNATAIRE_NOTIFIE, SIGNATAIRE_REFUSE, SIGNATAIRE_SIGNE,
        SIGNATURE_ANNULE,
    )
    if demande.statut == SIGNATURE_ANNULE or demande.is_expired:
        return _ged_noindex(Response(
            {'detail': "Ce lien de signature a expiré ou a été annulé."},
            status=status.HTTP_410_GONE))
    if signataire.statut in (SIGNATAIRE_SIGNE, SIGNATAIRE_REFUSE):
        return _ged_noindex(Response(
            {'detail': "Vous avez déjà traité cette demande.",
             'statut': signataire.statut},
            status=status.HTTP_410_GONE))

    if request.method == 'GET':
        return _ged_noindex(
            Response(_signataire_publique_payload(signataire),
                     status=status.HTTP_200_OK))

    if signataire.statut != SIGNATAIRE_NOTIFIE:
        return _ged_noindex(Response(
            {'detail': "Ce n'est pas encore votre tour de signer."},
            status=status.HTTP_403_FORBIDDEN))

    action_demandee = (request.data.get('action') or '').strip().lower()
    if action_demandee == 'refuser':
        try:
            signataire = services.refuser_signataire(
                signataire, motif=request.data.get('motif'))
        except ValueError as exc:
            return _ged_noindex(Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))
        return _ged_noindex(
            Response(_signataire_publique_payload(signataire),
                     status=status.HTTP_200_OK))

    if action_demandee == 'envoyer-code':
        # ZGED2 — envoie (ou dégrade proprement) le code d'authentification
        # extra de CE destinataire avant qu'il ne débloque la signature.
        resultat = services.envoyer_code_otp_signataire(signataire)
        return _ged_noindex(Response(resultat, status=status.HTTP_200_OK))

    if action_demandee == 'valider-code':
        try:
            signataire = services.valider_code_otp_signataire(
                signataire, request.data.get('code'))
        except ValueError as exc:
            return _ged_noindex(Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))
        return _ged_noindex(
            Response(_signataire_publique_payload(signataire),
                     status=status.HTTP_200_OK))

    if action_demandee == 'signer':
        try:
            signataire = services.signer_signataire(
                signataire,
                consentement=bool(request.data.get('consentement')),
                signature_texte=request.data.get('signature_texte', ''),
                signature_tracee=request.data.get('signature_tracee', ''),
                adresse_ip=services._adresse_ip_requete(request),
                user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:512])
        except ValueError as exc:
            return _ged_noindex(Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST))
        return _ged_noindex(
            Response(_signataire_publique_payload(signataire),
                     status=status.HTTP_200_OK))

    return _ged_noindex(Response(
        {'detail': "Action inconnue : 'signer', 'refuser', 'envoyer-code' ou "
                   "'valider-code' attendu."},
        status=status.HTTP_400_BAD_REQUEST))
