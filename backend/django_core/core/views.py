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
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    action,
)
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
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
    ApiUsagePlan,
    BackupRun,
    BrandedTemplate,
    ChangelogEntry,
    ChangelogRead,
    ConsentRecord,
    Dashboard,
    DataSubjectRequest,
    DeletionRecord,
    ModuleToggle,
    PaymentTransaction,
    RegistreTraitement,
    SavedQuery,
    ScheduledExport,
    TenantTheme,
)
from .serializers import (
    ApiUsagePlanSerializer,
    BackupRunSerializer,
    BrandedTemplateSerializer,
    ChangelogEntrySerializer,
    ConsentRecordSerializer,
    DashboardSerializer,
    DataSubjectRequestSerializer,
    DeletionRecordSerializer,
    ModuleToggleSerializer,
    PaymentTransactionSerializer,
    RegistreTraitementSerializer,
    SavedQuerySerializer,
    ScheduledExportSerializer,
    ScheduledJobSerializer,
    TenantThemeSerializer,
    TenantUsageSnapshotSerializer,
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
        from .formula import FormulaError
        try:
            rows = data_explorer.run_query(
                dataset, self.request.user.company, self.request.user, spec)
        except data_explorer.DatasetInconnu as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except (data_explorer.ChampNonAutorise, FormulaError) as exc:
            # XPLT11 — une mesure formule illégale (nœud interdit/variable
            # inconnue) renvoie 400, comme un champ hors liste blanche.
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


class ModuleCatalogViewSet(viewsets.ViewSet):
    """ODX3 — catalogue de modules (manifests fusionnés avec l'état société).

    Sans modèle propre : fusionne les manifests ``core.modules`` avec l'état
    ``ModuleToggle`` de la société de l'appelant. Aucune importation d'app
    domaine (les manifests sont lus par attribut sur les ``AppConfig``).

      * ``GET  …/modules/``                — catalogue installable + état actif ;
      * ``POST …/modules/{key}/activer/``  — active + fermeture des dépendances ;
      * ``POST …/modules/{key}/desactiver/`` — refuse en 400 si des modules
        actifs en dépendent (sauf ``?cascade=1``).

    Lecture ouverte à tout utilisateur authentifié (la SPA en a besoin) ;
    écriture réservée au palier admin/responsable. ``company`` toujours côté
    serveur, jamais du body.
    """

    def get_permissions(self):
        if self.action in ('list',):
            return [IsAuthenticated()]
        return [IsAdminOrResponsableTier()]

    def list(self, request):
        from . import feature_flags
        company = request.user.company
        return Response(feature_flags.catalogue_modules(company))

    @action(detail=True, methods=['post'], url_path='activer')
    def activer(self, request, pk=None):
        from . import feature_flags
        company = request.user.company
        try:
            actives = feature_flags.activer_module(company, pk)
        except feature_flags.DependencyError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'actives': actives})

    @action(detail=True, methods=['post'], url_path='desactiver')
    def desactiver(self, request, pk=None):
        from . import feature_flags
        company = request.user.company
        cascade = str(request.query_params.get('cascade', '')) in ('1', 'true')
        try:
            desactives = feature_flags.desactiver_module(
                company, pk, cascade=cascade)
        except feature_flags.DependencyError as exc:
            return Response(
                {'detail': str(exc), 'dependants': exc.dependents},
                status=status.HTTP_400_BAD_REQUEST)
        return Response({'desactives': desactives})


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


class ConsentRecordViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG394 — registre de consentement par société (loi 09-08 / CNDP).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    Réservé au palier admin/responsable (donnée de conformité sensible). Aucune
    importation d'app domaine : la personne est désignée par un identifiant
    générique (email/téléphone).
    """
    serializer_class = ConsentRecordSerializer
    permission_classes = [IsAdminOrResponsableTier]
    queryset = ConsentRecord.objects.all()


class DataSubjectRequestViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG394 — demandes de personnes concernées (accès/effacement).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    Réservé au palier admin/responsable. Aucune importation d'app domaine :
    l'export/effacement réel passe par les fournisseurs DSR enregistrés
    (``core.dsr``) — core agrège sans rien importer.

      * ``POST …/dsr-requests/{id}/traiter/`` — exécute la demande (accès →
        export agrégé ; effacement → suppression/anonymisation agrégée).
    """
    serializer_class = DataSubjectRequestSerializer
    permission_classes = [IsAdminOrResponsableTier]
    queryset = DataSubjectRequest.objects.all()

    @action(detail=True, methods=['post'])
    def traiter(self, request, pk=None):
        from . import dsr
        dsr_request = self.get_object()
        dsr.traiter_demande(dsr_request)
        return Response(self.get_serializer(dsr_request).data)


class RegistreTraitementViewSet(TenantMixin, viewsets.ModelViewSet):
    """XPLT23 — registre des traitements CNDP (loi 09-08).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    Réservé au palier admin/responsable (donnée de conformité). Aucune
    importation d'app domaine.

      * ``GET …/registre-traitements/export-csv/`` — export CSV du registre.
    """
    serializer_class = RegistreTraitementSerializer
    permission_classes = [IsAdminOrResponsableTier]
    queryset = RegistreTraitement.objects.all()
    pagination_class = None

    @action(detail=False, methods=['get'], url_path='export-csv')
    def export_csv(self, request):
        import csv
        from django.http import HttpResponse

        rows = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            'attachment; filename="registre-traitements-cndp.csv"')
        writer = csv.writer(response)
        writer.writerow([
            'code', 'finalite', 'base_legale', 'categories_donnees',
            'categories_personnes', 'destinataires', 'duree_conservation',
            'numero_recepisse', 'date_recepisse', 'actif',
        ])
        for r in rows:
            writer.writerow([
                r.code, r.finalite, r.base_legale, r.categories_donnees,
                r.categories_personnes, r.destinataires, r.duree_conservation,
                r.numero_recepisse,
                r.date_recepisse.isoformat() if r.date_recepisse else '',
                'oui' if r.actif else 'non',
            ])
        return response


class BackupRunViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG395 — sauvegarde/restauration en libre-service (par société).

    Multi-tenant : ``TenantMixin`` filtre par société et impose ``company``.
    Réservé au palier admin/responsable (opération sensible sur les données de
    la société). ``declenche_par`` est positionné à l'utilisateur courant à la
    création. Aucune importation d'app domaine : le runner ``core.backup``
    n'agrège que des datasets enregistrés (déjà scopés société).

      * ``POST …/sauvegardes/`` (kind=export) → crée + exécute la sauvegarde.
      * ``POST …/sauvegardes/`` (kind=restore) → trace une restauration (no-op
        tracé tant que le pipeline n'est pas branché — jamais d'écriture aveugle).
      * ``POST …/sauvegardes/{id}/relancer/`` → ré-exécute l'opération.
    """
    serializer_class = BackupRunSerializer
    permission_classes = [IsAdminOrResponsableTier]
    queryset = BackupRun.objects.all()

    def perform_create(self, serializer):
        run = serializer.save(
            company=self.request.user.company,
            declenche_par=self.request.user)
        self._executer(run)

    def _executer(self, run):
        from . import backup
        if run.kind == BackupRun.KIND_RESTORE:
            backup.executer_restauration(run)
        else:
            backup.executer_sauvegarde(run)

    @action(detail=True, methods=['post'])
    def relancer(self, request, pk=None):
        run = self.get_object()
        self._executer(run)
        run.refresh_from_db()
        return Response(self.get_serializer(run).data)


class SystemStatusViewSet(viewsets.ViewSet):
    """FG397 — page d'état / santé système (services + incidents récents).

    Infra TRANSVERSE : la santé des services (db/cache/broker/stockage/
    monitoring) est globale ; les incidents récents sont bornés à la société de
    l'utilisateur. Ouvert à tout utilisateur authentifié (lecture seule).
    Aucune importation d'app domaine : tout passe par ``core.health``.

      * ``GET …/status/``  — santé des services + état global + incidents.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        from . import health
        services = health.check_services()
        company = getattr(request.user, 'company', None)
        return Response({
            'global': health.overall_status(services),
            'services': services,
            'incidents': health.recent_incidents(company=company),
        })


# YOPSB14 — endpoints readiness/liveness LÉGERS, NON authentifiés, jamais de
# données société. Distincts de SystemStatusViewSet (agrégat riche,
# authentifié) : ceux-ci sont conçus pour être sondés par nginx/Caddy AVANT
# de router une requête (évite les 502 après recréation de conteneur, notés
# en mémoire projet). Exemptés d'auth ET de throttle (DRF @api_view avec
# AllowAny + authentication_classes=[] court-circuite l'auth par défaut).
@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def health_live(request):
    """``GET /api/django/core/health/live/`` — 200 IMMÉDIAT, process vivant.

    Ne touche JAMAIS la base de données (contrairement à /health/ready/) :
    répond même si Postgres est down, pour distinguer "le process Django a
    planté" de "la DB est indisponible"."""
    return Response({'status': 'live'})


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def health_ready(request):
    """``GET /api/django/core/health/ready/`` — 200 si la DB répond
    (``core.health._check_db``), 503 sinon. Conçu pour un probe
    nginx/Caddy AVANT de router du trafic vers ce worker."""
    from . import health
    db_check = health.check_db()
    if db_check['status'] == health.STATUS_DOWN:
        return Response({'status': 'not-ready', 'detail': db_check['detail']},
                        status=503)
    return Response({'status': 'ready'})


class ApiUsagePlanViewSet(TenantMixin, viewsets.GenericViewSet):
    """FG398 — plan de tarif API & analytics d'usage (par société).

    Multi-tenant : ``TenantMixin`` impose ``company``. Le plan est un SINGLETON
    par société (OneToOne). Écriture admin/responsable ; lecture authentifiée.
    Aucune importation d'app domaine : l'usage est agrégé via ``core.api_usage``
    (la clé d'API est une string-FK).

      * ``GET …/api-usage/plan/``        — plan de quota de la société.
      * ``PUT/PATCH …/api-usage/plan/``  — met à jour le plan (admin/responsable).
      * ``GET …/api-usage/analytics/``   — analytics d'usage (par clé + total).
    """
    serializer_class = ApiUsagePlanSerializer
    queryset = ApiUsagePlan.objects.all()

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'POST'):
            return [IsAdminOrResponsableTier()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='plan')
    def plan(self, request):
        from . import api_usage
        company = request.user.company
        if request.method == 'GET':
            plan = api_usage.plan_pour_societe(company)
            return Response(ApiUsagePlanSerializer(plan).data)
        plan = api_usage.plan_pour_societe(company)
        partial = request.method == 'PATCH'
        serializer = ApiUsagePlanSerializer(
            plan, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(company=company)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def analytics(self, request):
        from . import api_usage
        return Response(api_usage.analytics(request.user.company))


class ChangelogViewSet(viewsets.ModelViewSet):
    """FG399 — journal des nouveautés in-app (changelog) + suivi de lecture.

    Le changelog est GLOBAL au produit (aucune portée société) : la lecture est
    ouverte à tout utilisateur authentifié et ne renvoie que les notes publiées ;
    l'écriture (publication) est réservée au palier admin. Le suivi de lecture
    est PAR UTILISATEUR. Aucune importation d'app domaine.

      * ``GET …/changelog/``            — notes publiées + drapeau ``lu``.
      * ``GET …/changelog/non_lues/``   — compte de notes non lues.
      * ``POST …/changelog/{id}/marquer_lu/`` — accuse lecture d'une note.
      * ``POST …/changelog/marquer_tout_lu/`` — accuse lecture de tout.
    """
    serializer_class = ChangelogEntrySerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'non_lues', 'marquer_lu',
                           'marquer_tout_lu'):
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = ChangelogEntry.objects.all()
        # Les non-admins ne voient que les notes publiées.
        user = self.request.user
        if not (user.is_superuser or getattr(user, 'is_staff', False)):
            if self.action in ('list', 'retrieve', 'non_lues'):
                qs = qs.filter(publie=True)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ids = set(
            ChangelogRead.objects.filter(user=self.request.user)
            .values_list('entry_id', flat=True))
        ctx['entries_lues'] = ids
        return ctx

    @action(detail=False, methods=['get'])
    def non_lues(self, request):
        lues = set(
            ChangelogRead.objects.filter(user=request.user)
            .values_list('entry_id', flat=True))
        total = ChangelogEntry.objects.filter(publie=True).exclude(
            pk__in=lues).count()
        return Response({'non_lues': total})

    @action(detail=True, methods=['post'])
    def marquer_lu(self, request, pk=None):
        entry = self.get_object()
        ChangelogRead.objects.get_or_create(user=request.user, entry=entry)
        return Response({'lu': True})

    @action(detail=False, methods=['post'])
    def marquer_tout_lu(self, request):
        entries = ChangelogEntry.objects.filter(publie=True)
        for entry in entries:
            ChangelogRead.objects.get_or_create(
                user=request.user, entry=entry)
        return Response({'non_lues': 0})


# YHARD5 — tableau « Secrets & rotation », admin-only. Ne renvoie JAMAIS la
# valeur d'un secret — seulement le fournisseur, le nom de variable
# d'environnement (secret_ref) et l'échéance de rotation. Company-scopée.
@api_view(['GET'])
@permission_classes([IsAdminRole])
def secrets_rotation_due(request):
    """``GET /api/django/core/secrets/rotation/`` — intégrations échues."""
    from . import integrations as integrations_infra

    user = request.user
    company = user.company if user.company_id else None
    if company is None and not user.is_superuser:
        return Response({'count': 0, 'results': []})

    if company is not None:
        due = integrations_infra.secrets_due_for_rotation(company)
    else:
        # Superuser sans société : agrège toutes les sociétés (vue globale).
        from authentication.models import Company
        due = []
        for c in Company.objects.all():
            due.extend(integrations_infra.secrets_due_for_rotation(c))

    return Response({'count': len(due), 'results': due})


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# YHARD6 — endpoint /metrics (format texte Prometheus). JAMAIS public : soit un
# utilisateur admin authentifié (session/JWT), soit l'IP du caller figure dans
# ``settings.METRICS_ALLOWED_IPS`` (scrape Prometheus sans session). Vide par
# défaut = admin-only (aucune IP autorisée). Ne plante jamais : une IP hors
# liste + non-admin reçoit 403, jamais une 500.
@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def metrics_view(request):
    from django.conf import settings
    from django.http import HttpResponse

    from authentication.cookie_auth import CookieJWTAuthentication

    from . import metrics as metrics_infra

    allowed_ips = set(getattr(settings, 'METRICS_ALLOWED_IPS', []) or [])
    ip_ok = bool(allowed_ips) and _client_ip(request) in allowed_ips

    admin_ok = False
    if not ip_ok:
        try:
            auth_result = CookieJWTAuthentication().authenticate(request)
        except Exception:  # noqa: BLE001 — jeton absent/invalide → non-admin
            auth_result = None
        if auth_result is not None:
            user, _token = auth_result
            admin_ok = bool(getattr(user, 'is_admin_role', False))

    if not (ip_ok or admin_ok):
        return Response({'detail': 'Accès /metrics non autorisé.'}, status=403)

    body = metrics_infra.render_prometheus_text()
    return HttpResponse(body, content_type='text/plain; version=0.0.4')


# ── NTPLT6 — Endpoint superuser des compteurs d'usage par tenant (metering) ──


class _IsSuperUser(BasePermission):
    """Permission stricte : superuser Django uniquement (jamais un tenant)."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and user.is_superuser)


# ── NTPLT19 — Endpoint superuser des statistiques DB (introspection READ-ONLY) ─
@api_view(['GET'])
@permission_classes([_IsSuperUser])
def db_stats_view(request):
    """Top requêtes (pg_stat_statements), tailles de tables, index inutilisés.

    SUPERUSER only, JAMAIS exposé aux tenants. Lecture seule. Dégrade proprement
    si ``pg_stat_statements`` n'est pas préchargée (message par section)."""
    from . import db_stats
    return Response(db_stats.collect_db_stats())


class TenantUsageSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """NTPLT6 — instantanés d'usage par tenant (lecture seule, SUPERUSER only).

    Fondation technique de N100 (plans/billing, différé). JAMAIS exposé à un
    tenant : c'est une vue transverse à toutes les sociétés, réservée à
    l'exploitant de l'instance. Filtrable par ``?company=<id>`` et
    ``?jour=AAAA-MM-JJ``. Une action ``snapshot`` déclenche un calcul immédiat
    (utile hors du beat nocturne).

      * ``GET  usage/``           — liste des instantanés (toutes sociétés)
      * ``GET  usage/{id}/``      — un instantané
      * ``POST usage/snapshot/``  — calcule/rafraîchit l'instantané du jour
    """
    serializer_class = TenantUsageSnapshotSerializer
    permission_classes = [_IsSuperUser]

    def get_queryset(self):
        from .models import TenantUsageSnapshot
        qs = TenantUsageSnapshot.objects.select_related('company').all()
        company = self.request.query_params.get('company')
        if company:
            qs = qs.filter(company_id=company)
        jour = self.request.query_params.get('jour')
        if jour:
            qs = qs.filter(jour=jour)
        return qs

    @action(detail=False, methods=['post'])
    def snapshot(self, request):
        """Calcule/rafraîchit l'instantané du jour pour toutes les sociétés."""
        from . import usage
        done = usage.snapshot_all()
        return Response({'companies': len(done)}, status=status.HTTP_200_OK)
