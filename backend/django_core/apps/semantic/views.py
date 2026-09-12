"""Surface HTTP de la couche sémantique — des LECTURES, et rien d'autre.

Le CRUD des métriques (NTDATA10) est une tâche séparée : cette liste dit
exactement ce qui est servi aujourd'hui.

  * ``GET semantic/metriques/<id>/versions/`` (NTDATA9) — l'historique figé
    des définitions successives d'une métrique.

CHAQUE ROUTE A SA PROPRE CLASSE : deux routes branchées sur la MÊME vue
produisent le même ``operationId`` dans le schéma OpenAPI, et la collision fait
échouer la génération (précédent NTDATA5).

Toutes les lectures sont bornées à ``request.user.company`` : une métrique est
company-scopée, son historique l'est donc aussi.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsResponsableOrAdmin

from . import services
from .models import MetricDefinition


class MetriqueVersionsView(APIView):
    """NTDATA9 — l'historique FIGÉ des définitions d'une métrique.

    ``GET /semantic/metriques/<id>/versions/`` rend les versions de la plus
    récente à la plus ancienne : ce que valait la définition, quand elle a été
    figée, et par qui (vide quand l'édition est venue d'un chemin sans acteur
    identifié — le seeder, l'admin, un script).

    Une métrique d'une AUTRE société est un 404, jamais un 403 : répondre
    « interdit » confirmerait son existence.
    """

    permission_classes = [IsResponsableOrAdmin]

    @extend_schema(
        responses=inline_serializer('MetriqueVersionsReponse', {
            'metrique': serializers.CharField(),
            'libelle': serializers.CharField(),
            'nb_versions': serializers.IntegerField(),
            'versions': serializers.JSONField(),
        }))
    def get(self, request, pk=None):
        definition = MetricDefinition.objects.filter(
            pk=pk, company=request.user.company).first()
        if definition is None:
            return Response({'detail': 'Métrique introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        versions = [
            {
                'version': version.version,
                'libelle': version.libelle,
                'dataset': version.dataset,
                'mesure': version.mesure,
                'filtres': version.filtres,
                'unite': version.unite,
                'auteur': (getattr(version.auteur, 'username', '')
                           if version.auteur_id else ''),
                'figee_le': version.date_creation.isoformat(),
            }
            for version in services.versions_metrique(definition)
        ]
        return Response({
            'metrique': definition.cle,
            'libelle': definition.libelle,
            'nb_versions': len(versions),
            'versions': versions,
        })
