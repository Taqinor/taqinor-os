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

from . import jobs as jobs_infra
from . import workflow_templates
from .mixins import TenantMixin
from .models import Dashboard
from .serializers import (
    DashboardSerializer,
    ScheduledJobSerializer,
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
