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
from rest_framework.response import Response

from authentication.permissions import IsAdminRole

from . import jobs as jobs_infra
from .serializers import ScheduledJobSerializer


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
