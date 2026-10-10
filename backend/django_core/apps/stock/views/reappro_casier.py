"""NTWMS40 — casiers picking dus, seuils, et tâches de réappro interne."""
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework.parsers import JSONParser
from rest_framework import serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.serializers import CompanyScopedRelationsMixin
from ..openapi_helpers import INT, P, STR
from core.viewsets import CompanyScopedModelViewSet

from ..models import SeuilReapproCasier, TacheReapproInterne

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class SeuilReapproCasierSerializer(CompanyScopedRelationsMixin,
                                   serializers.ModelSerializer):
    bin_code = serializers.CharField(source='bin.code', read_only=True,
                                     default='')

    class Meta:
        model = SeuilReapproCasier
        fields = ['id', 'bin', 'bin_code', 'produit', 'seuil',
                  'quantite_cible', 'actif', 'created_at']
        read_only_fields = ['created_at']


class TacheReapproInterneSerializer(CompanyScopedRelationsMixin,
                                    serializers.ModelSerializer):
    bin_cible_code = serializers.CharField(source='bin_cible.code',
                                           read_only=True, default='')
    bin_source_code = serializers.CharField(source='bin_source.code',
                                            read_only=True, default='')

    class Meta:
        model = TacheReapproInterne
        fields = ['id', 'produit', 'bin_cible', 'bin_cible_code',
                  'bin_source', 'bin_source_code', 'quantite', 'statut',
                  'note', 'created_at']
        # ASTK213 — le statut ne change QUE par l'action `executer` (jamais
        # un PATCH qui fermerait la tâche sans aucun mouvement).
        read_only_fields = ['statut', 'note', 'created_at']


@extend_schema_view(list=extend_schema(parameters=[P('bin', INT)]))
class SeuilReapproCasierViewSet(CompanyScopedModelViewSet):
    """Seuils de réappro par casier de picking. Poser un seuil, c'est
    DÉCLARER le casier comme casier de prélèvement."""
    queryset = SeuilReapproCasier.objects.select_related(
        'bin', 'produit').all()
    serializer_class = SeuilReapproCasierSerializer
    ordering = ['bin_id']

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        # Filtrage MANUEL (aucun DjangoFilterBackend branché ici).
        qs = super().get_queryset()
        bin_id = self.request.query_params.get('bin')
        if bin_id:
            qs = qs.filter(bin_id=bin_id)
        return qs


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR)]))
class TacheReapproInterneViewSet(CompanyScopedModelViewSet):
    """Ordres de réappro interne (magasin → casier picking).

    Ce sont des ORDRES DE TRAVAIL : ils ne bougent aucun stock par eux-mêmes,
    le déplacement réel passe par le poste scanner comme tout mouvement.
    """
    queryset = TacheReapproInterne.objects.select_related(
        'produit', 'bin_cible', 'bin_source').all()
    serializer_class = TacheReapproInterneSerializer
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['executer']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @extend_schema(request=None, responses={
        200: inline_serializer('StockTacheReapproExecutee', {
            'id': serializers.IntegerField(),
            'statut': serializers.CharField(),
            'mouvement_id': serializers.IntegerField(),
            'bin_source': serializers.IntegerField(),
            'bin_cible': serializers.IntegerField(),
            'quantite': serializers.IntegerField(),
        }),
    })
    @action(detail=True, methods=['post'], url_path='executer')
    def executer(self, request, pk=None):
        """ASTK213 — exécute la tâche UNE fois : transfert casier source →
        casier cible (chemin du poste scanner) puis statut ``faite``. Second
        appel → 409 « Tâche déjà exécutée. », sans second mouvement."""
        from ..services_reappro_casier import (
            TacheDejaExecutee, executer_tache_reappro_interne,
        )
        tache = self.get_object()  # 404 hors société
        try:
            resultat = executer_tache_reappro_interne(
                company=request.user.company, tache_id=tache.pk,
                user=request.user)
        except TacheDejaExecutee as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat)


@extend_schema(request=None, responses={
    200: inline_serializer('StockCasiersAReapprovisionner', {
        'casiers': serializers.ListField(child=serializers.DictField()),
        'taches_creees': serializers.IntegerField(),
    }),
})
@api_view(['GET', 'POST'])
@permission_classes([IsResponsableOrAdmin])
def casiers_a_reapprovisionner_view(request):
    """NTWMS40 — GET liste les casiers picking sous leur seuil ;
    POST génère les tâches de réappro interne correspondantes (idempotent :
    jamais deux tâches ouvertes sur le même casier)."""
    from ..services_reappro_casier import (
        casiers_picking_a_reapprovisionner, generer_taches_reappro_interne,
    )

    company = request.user.company
    creees = 0
    if request.method == 'POST':
        creees = len(generer_taches_reappro_interne(company, request.user))
    return Response({
        'casiers': casiers_picking_a_reapprovisionner(company),
        'taches_creees': creees,
    })
