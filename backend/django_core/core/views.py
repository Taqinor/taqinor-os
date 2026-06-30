"""Vues de la couche fondation ``core``.

FG368 — gestion des tâches planifiées (Celery Beat).

``ScheduledJobViewSet`` expose, pour l'écran Paramètres « Tâches planifiées » :

  * ``GET  …/jobs/``          — liste des jobs configurés (digests/rapports/
    monitoring…), forme normalisée ;
  * ``POST …/jobs/run/``      — exécution MANUELLE d'un job (``{"task": "…"}``).

Les jobs sont une infra GLOBALE (pas de portée société) : l'accès est donc
réservé au palier administrateur / superutilisateur (``IsAdminRole``).
L'exécution manuelle ne fait jamais planter le serveur si le broker est
injoignable — elle renvoie alors 503 avec un message clair.

Découplage : aucune importation d'app domaine ici — seulement l'infra Celery
via ``core.jobs`` (qui fait ``from celery import current_app``). ``core`` reste
une couche de base (import-linter).
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminOrResponsableTier,
    IsAdminRole,
)

from django.db.models import Q

from . import bulk_edit as bulk_edit_infra
from . import data_explorer
from . import jobs as jobs_infra
from . import payment as payment_infra
from . import scheduled_export as scheduled_export_infra
from . import trash as trash_infra
from . import workflow_templates
from .mixins import TenantMixin
from .models import (
    BrandedTemplate,
    Dashboard,
    DeletionRecord,
    ModuleToggle,
    PaymentTransaction,
    SavedQuery,
    ScheduledExport,
    TenantTheme,
)
from .serializers import (
    BrandedTemplateSerializer,
    DashboardSerializer,
    DeletionRecordSerializer,
    ModuleToggleSerializer,
    PaymentTransactionSerializer,
    SavedQuerySerializer,
    ScheduledExportSerializer,
    ScheduledJobSerializer,
    TenantThemeSerializer,
    WorkflowTemplateSerializer,
)


class ScheduledJobViewSet(viewsets.ViewSet):
    """Jobs Celery Beat (infra globale, admin uniquement).

    Sans modèle : la source de vérité est la configuration Celery, pas une
    table métier. Pas de scoping société (infra transverse).
    """
    permission_classes = [IsAdminRole]

    def list(self, request):
        data = jobs_infra.list_jobs()
        return Response(ScheduledJobSerializer(data, many=True).data)

    @action(detail=False, methods=['post'])
    def run(self, request):
        """Déclenche manuellement un job planifié.

        Corps : ``{"task": "<chemin.tache.celery>"}``. Seules les tâches
        réellement planifiées sont autorisées (liste blanche). Broker
        injoignable → 503 (jamais 500).
        """
        task_name = (request.data or {}).get('task')
        if not task_name:
            return Response(
                {'detail': "Champ « task » requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            task_id = jobs_infra.run_job(task_name)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as exc:
            # Broker indisponible / erreur de transport : on dégrade en 503.
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            {'task': task_name, 'task_id': task_id, 'status': 'envoyé'},
            status=status.HTTP_202_ACCEPTED,
        )


class WorkflowTemplateViewSet(viewsets.ViewSet):
    """FG369 — bibliothèque de modèles de workflow installables en un clic.

    Sans modèle propre : la source de vérité est le catalogue de DONNÉES
    ``core.workflow_templates`` (templates GLOBAUX, sans société). L'install
    matérialise un ``WorkflowDefinition`` FG366 + ses étapes POUR LA SOCIÉTÉ DE
    L'UTILISATEUR (imposée côté serveur, jamais issue du corps de requête).

      * ``GET  …/workflow-templates/``                — liste des modèles
        disponibles (lecture seule, tout utilisateur authentifié) ;
      * ``POST …/workflow-templates/installer/``      — installe un modèle
        (corps ``{"code": "<code>"}``) pour la société de l'utilisateur ;
        réservé au palier admin/responsable ; idempotent (re-install = no-op).

    Découplage : aucune importation d'app domaine — seulement le catalogue de
    données ``core.workflow_templates`` (qui ne touche que les modèles FG366).
    ``core`` reste une couche de base (import-linter).
    """

    def get_permissions(self):
        # Lecture : tout utilisateur authentifié ; install : admin/responsable.
        if getattr(self, 'action', None) == 'installer':
            return [IsAdminOrResponsableTier()]
        return [IsAuthenticated()]

    def list(self, request):
        data = workflow_templates.liste_modeles_workflow()
        return Response(WorkflowTemplateSerializer(data, many=True).data)

    @action(detail=False, methods=['post'])
    def installer(self, request):
        """Installe un modèle de workflow pour la société de l'utilisateur.

        Corps : ``{"code": "<code-du-modele>"}``. ``company`` est TOUJOURS
        imposée côté serveur (``request.user.company``) — jamais lue du corps.
        Idempotent : réinstaller un modèle déjà présent ne crée aucun doublon
        et renvoie 200 (au lieu de 201).
        """
        code = (request.data or {}).get('code')
        if not code:
            return Response(
                {'detail': "Champ « code » requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response(
                {'detail': "Utilisateur sans société."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            definition, created = workflow_templates.installer_modele_workflow(
                company, code)
        except workflow_templates.ModeleWorkflowInconnu as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                'code': definition.code,
                'nom': definition.nom,
                'definition_id': definition.pk,
                'created': created,
                'nb_etapes': definition.steps.count(),
            },
            status=(status.HTTP_201_CREATED if created
                    else status.HTTP_200_OK),
        )


class DashboardViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG381 — dashboards sans-code, sauvegardés par utilisateur/société.

    Multi-tenant : ``TenantMixin`` filtre déjà par société et impose
    ``company`` à la création. On affine la lecture : un utilisateur voit SES
    dashboards personnels + ceux PARTAGÉS de sa société (les dashboards
    personnels d'autrui restent privés). ``owner`` est positionné à
    l'utilisateur courant à la création (jamais lu du corps).
    """
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]
    queryset = Dashboard.objects.all()
    pagination_class = None  # petite liste par utilisateur — renvoyée à plat.

    def get_queryset(self):
        qs = super().get_queryset()  # déjà filtré par société (TenantMixin).
        user = self.request.user
        # Personnels de l'utilisateur + partagés société + dashboards société
        # sans propriétaire.
        return qs.filter(
            Q(owner=user) | Q(partage=True) | Q(owner__isnull=True)
        ).distinct()

    def perform_create(self, serializer):
        # company imposée côté serveur (TenantMixin) ; owner = utilisateur courant.
        serializer.save(company=self.request.user.company,
                        owner=self.request.user)

    def perform_update(self, serializer):
        # Ne jamais réécrire company/owner depuis le corps.
        serializer.save(company=self.request.user.company)


class PaymentTransactionViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG370 — paiement carte en ligne d'une facture (CMI / Payzone).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company`` à
    la création. La création initie la transaction auprès du PSP (no-op propre
    si aucun compte marchand n'est configuré — la transaction reste « initiée »
    avec un détail explicite, jamais d'appel réseau). Aucune importation d'app
    domaine : la cible (facture) est désignée via ``content_type``/``object_id``
    et le rapprochement comptable passe par l'événement ``payment_captured``.
    """
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]
    queryset = PaymentTransaction.objects.all()

    def perform_create(self, serializer):
        # company imposée côté serveur ; on initie aussitôt auprès du PSP.
        transaction = serializer.save(company=self.request.user.company)
        payment_infra.initier(transaction)

    @action(detail=True, methods=['post'])
    def rafraichir(self, request, pk=None):
        """Interroge le PSP et synchronise le statut (no-op si non configuré)."""
        transaction = self.get_object()
        provider = payment_infra._provider_for(transaction)
        if provider is not None:
            res = provider.fetch_status(transaction)
            if res.get('ok') and res.get('statut'):
                transaction.statut = res['statut']
                transaction.save(update_fields=['statut', 'updated_at'])
        return Response(self.get_serializer(transaction).data)


class SavedQueryViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG382 — explorateur de données : requêtes ad-hoc sauvegardées + run.

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    Visibilité personnelle/société comme ``Dashboard``. Aucune importation
    d'app domaine : l'exécution passe par ``core.data_explorer`` sur des
    datasets enregistrés par les apps métier (querysets déjà scopés société).

      * ``GET  …/saved-queries/datasets/`` — catalogue des datasets disponibles ;
      * ``POST …/saved-queries/{id}/run/`` — exécute la requête sauvegardée ;
      * ``POST …/saved-queries/run/``      — exécute une spec ad-hoc (corps
        ``{"dataset": "...", "spec": {...}}``) sans sauvegarder.
    """
    serializer_class = SavedQuerySerializer
    permission_classes = [IsAuthenticated]
    queryset = SavedQuery.objects.all()
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        return qs.filter(
            Q(owner=user) | Q(partage=True) | Q(owner__isnull=True)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company,
                        owner=self.request.user)

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def datasets(self, request):
        return Response(data_explorer.list_datasets())

    def _execute(self, dataset, spec):
        try:
            rows = data_explorer.run_query(
                dataset, self.request.user.company, self.request.user, spec)
        except data_explorer.DatasetInconnu as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except data_explorer.ChampNonAutorise as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'rows': rows})

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        obj = self.get_object()
        return self._execute(obj.dataset, obj.spec)

    @action(detail=False, methods=['post'], url_path='run')
    def run_adhoc(self, request):
        dataset = (request.data or {}).get('dataset')
        if not dataset:
            return Response({'detail': "Champ « dataset » requis."},
                            status=status.HTTP_400_BAD_REQUEST)
        return self._execute(dataset, (request.data or {}).get('spec') or {})


class ScheduledExportViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG383 — extraits planifiés vers SFTP/S3 (CRUD + run manuel, gated).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    L'écriture (création/planification) est réservée au palier admin/responsable
    (une destination externe est sensible). Aucune importation d'app domaine :
    données via ``core.data_explorer`` (datasets enregistrés), livraison via le
    runner ``core.scheduled_export`` (no-op propre si non configuré).

      * ``POST …/scheduled-exports/{id}/executer/`` — exécute l'extrait
        maintenant (no-op si la destination n'est pas configurée).
    """
    serializer_class = ScheduledExportSerializer
    queryset = ScheduledExport.objects.all()
    pagination_class = None

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrResponsableTier()]

    @action(detail=True, methods=['post'])
    def executer(self, request, pk=None):
        export = self.get_object()
        scheduled_export_infra.executer(export)
        return Response(self.get_serializer(export).data)


class TrashViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """FG388 — corbeille par société + restauration + fenêtre d'undo.

    Multi-tenant : ``TenantMixin`` filtre par société. Lecture seule + une
    action de restauration ; aucune importation d'app domaine — la cible est
    restaurée dynamiquement via ``content_type`` (``core.trash``).

      * ``GET  …/corbeille/``            — entrées non restaurées de la société ;
      * ``GET  …/corbeille/?undo=1``     — uniquement la fenêtre d'« annuler » ;
      * ``POST …/corbeille/{id}/restaurer/`` — restaure l'objet d'origine.
    """
    serializer_class = DeletionRecordSerializer
    permission_classes = [IsAuthenticated]
    queryset = DeletionRecord.objects.all()
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset().filter(restored_at__isnull=True)
        if self.request.query_params.get('undo'):
            ids = trash_infra.dans_fenetre_undo(
                self.request.user.company).values_list('id', flat=True)
            qs = qs.filter(id__in=list(ids))
        return qs

    @action(detail=True, methods=['post'])
    def restaurer(self, request, pk=None):
        record = self.get_object()
        obj = trash_infra.restaurer(record)
        record.refresh_from_db()
        return Response({
            'restored': obj is not None,
            'record': self.get_serializer(record).data,
        })


class BulkEditViewSet(viewsets.ViewSet):
    """FG389 — édition de champ en masse, généralisée (sans modèle propre).

    Aucune importation d'app domaine : opère sur des cibles ENREGISTRÉES par les
    apps métier (``core.bulk_edit``), chacune fournissant un queryset déjà scopé
    société + une liste blanche de champs modifiables. L'écriture est bornée au
    queryset scopé (un id hors société est ignoré).

      * ``GET  …/bulk-edit/targets/`` — cibles éditables + champs autorisés ;
      * ``POST …/bulk-edit/appliquer/`` — corps
        ``{"target": "...", "ids": [...], "changes": {champ: valeur}}``.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def targets(self, request):
        return Response(bulk_edit_infra.list_bulk_targets())

    @action(detail=False, methods=['post'])
    def appliquer(self, request):
        body = request.data or {}
        target = body.get('target')
        if not target:
            return Response({'detail': "Champ « target » requis."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            count = bulk_edit_infra.apply_bulk_edit(
                target, request.user.company, request.user,
                body.get('ids') or [], body.get('changes') or {})
        except bulk_edit_infra.CibleInconnue as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except bulk_edit_infra.ChampNonModifiable as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'modifies': count})


class ModuleToggleViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG391 — flags de modules par société (activation/désactivation).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    L'écriture est réservée au palier admin/responsable (paramétrage société) ;
    la lecture est ouverte à tout utilisateur authentifié pour que la SPA sache
    quels modules afficher. Aucune importation d'app domaine : ``module`` est
    une clé libre.
    """
    serializer_class = ModuleToggleSerializer
    queryset = ModuleToggle.objects.all()
    pagination_class = None

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrResponsableTier()]


class TenantThemeViewSet(TenantMixin, viewsets.GenericViewSet):
    """FG392 — thème white-label par société (singleton, lecture/upsert).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    Le thème est un SINGLETON par société (OneToOne) : on n'expose pas un CRUD
    par id mais une action sur « le thème de ma société » :

      * ``GET …/theme/courant/``  — thème de la société (défauts vides sinon),
        ouvert à tout utilisateur authentifié (la SPA en a besoin) ;
      * ``PUT/PATCH …/theme/courant/`` — crée/met à jour (admin/responsable).

    Aucune importation d'app domaine : ``core`` reste fondation.
    """
    serializer_class = TenantThemeSerializer
    queryset = TenantTheme.objects.all()

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'POST'):
            return [IsAdminOrResponsableTier()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='courant')
    def courant(self, request):
        company = request.user.company
        theme = TenantTheme.objects.filter(company=company).first()
        if request.method == 'GET':
            if theme is None:
                # Pas encore de thème : renvoyer des défauts vides (jamais 404).
                return Response(TenantThemeSerializer(TenantTheme()).data)
            return Response(TenantThemeSerializer(theme).data)
        partial = request.method == 'PATCH'
        serializer = TenantThemeSerializer(
            theme, data=request.data, partial=partial or theme is None)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=company)
        return Response(serializer.data)


class BrandedTemplateViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG393 — éditeur de modèles imprimables/brandés (PDF/email/WhatsApp).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    L'écriture est réservée au palier admin/responsable ; la lecture est ouverte
    à tout utilisateur authentifié. Aucune importation d'app domaine : le rendu
    passe par le moteur SÛR ``core.templating`` (substitution littérale).

      * ``POST …/branded-templates/{id}/preview/`` — rend le modèle avec un
        contexte d'exemple (corps ``{"context": {...}}``).
    """
    serializer_class = BrandedTemplateSerializer
    queryset = BrandedTemplate.objects.all()
    pagination_class = None

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrResponsableTier()]

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        from . import templating
        template = self.get_object()
        context = (request.data or {}).get('context') or {}
        sujet, corps = templating.rendre_modele(template, context)
        return Response({'sujet': sujet, 'corps': corps})
