"""API REST de la GED — tout scopé société côté serveur.

Lecture : tout rôle authentifié. Écriture : responsable/admin. La société est
TOUJOURS posée côté serveur (TenantMixin) — jamais lue du corps de requête.
Les dossiers (Folder) ont un chemin matérialisé recalculé côté serveur, et les
versions de document sont numérotées + déduppées via `services`.
"""
from django.http import HttpResponse
from rest_framework import filters, status, viewsets
from rest_framework.decorators import (
    action, api_view, permission_classes, throttle_classes,
)
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
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
    Cabinet, Coffre, DemandeApprobation, Document, DocumentLien, DocumentTag,
    DocumentTagAssignment, DocumentVersion, Folder, PartageGed,
)
from .serializers import (
    CabinetSerializer, CoffreSerializer, DemandeApprobationSerializer,
    DocumentLienSerializer, DocumentSerializer,
    DocumentTagAssignmentSerializer, DocumentTagSerializer,
    DocumentVersionSerializer, FolderSerializer, PartageGedSerializer,
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
        if self.action in READ_ACTIONS or self.action == 'descendants':
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
    search_fields = ['nom', 'description']
    ordering_fields = ['nom', 'created_at', 'updated_at']

    def get_permissions(self):
        # `recherche`/`semantique`/`historique`/`check_out`/`check_in` lisibles
        # par tout rôle authentifié ; écriture réservée aux responsables/admins.
        if self.action in READ_ACTIONS or self.action in (
                'recherche', 'semantique', 'historique', 'demandes'):
            return [IsAnyRole()]
        # check_out/check_in : tout rôle peut extraire/libérer ses propres docs.
        if self.action in ('check_out', 'check_in'):
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
        document = serializer.save()
        # GED11 — réindexe après modification (nom/description/métadonnées).
        services.update_search_vector(document)
        # GED12 — réindexe l'embedding sémantique (no-op sans clé).
        services.index_embedding(document)
        # FG352 — réindexe les fragments RAG/DocQA (no-op sans clé).
        services.index_document_chunks(document)

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
        return Response(
            DocumentSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

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
        """FG352 — Récupération RAG / DocQA : top-k fragments pour une question.

        `GET …/documents/docqa/?q=<question>&k=<n>`. Renvoie les fragments de
        documents (`DocumentChunk`) les plus proches de la question (distance
        cosinus, magasin pgvector partagé), bornés aux documents visibles de
        l'utilisateur (ACL coffre-fort + société). KEY-GATED : sans clé
        d'embedding, `enabled` est faux et `results` est vide (no-op propre,
        aucun coût). Réutilise `selectors.retrieve_chunks`."""
        query = request.query_params.get('q', '')
        try:
            k = int(request.query_params.get('k', 5))
        except (TypeError, ValueError):
            k = 5
        chunks = selectors.retrieve_chunks(request.user, query, limit=k)
        results = [{
            'document': c.document_id,
            'document_nom': c.document.nom,
            'chunk_index': c.chunk_index,
            'texte': c.texte,
            'distance': getattr(c, 'distance', None),
        } for c in chunks]
        return Response({
            'enabled': services.embedding_enabled(),
            'results': results,
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
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DocumentVersionSerializer(
                new_version, context={'request': request}).data,
            status=status.HTTP_201_CREATED)

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
        except PermissionError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        doc.refresh_from_db()
        return Response(
            DocumentSerializer(doc, context={'request': request}).data)

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
            demande = services.request_review(
                document, user=request.user, approbateur=approbateur,
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

        # Formats affichables inline (PDF, images, texte). Tout le reste → attachment.
        _INLINE_MIMES = {
            'application/pdf',
            'image/png', 'image/jpeg', 'image/webp', 'image/gif',
            'text/plain', 'text/csv', 'text/html',
        }
        disposition = (
            'inline' if mime in _INLINE_MIMES else 'attachment'
        )

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
            dem = services.approve_demande(
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
    disposition = 'inline' if mime in _INLINE_MIMES else 'attachment'

    resp = HttpResponse(data, content_type=mime)
    resp['Content-Disposition'] = f'{disposition}; filename="{safe_name}"'
    resp['X-Content-Type-Options'] = 'nosniff'
    return _ged_noindex(resp)
