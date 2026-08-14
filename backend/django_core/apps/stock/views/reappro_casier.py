"""NTWMS40 — casiers picking dus, seuils, et tâches de réappro interne."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import SeuilReapproCasier, TacheReapproInterne

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class SeuilReapproCasierSerializer(serializers.ModelSerializer):
    bin_code = serializers.CharField(source='bin.code', read_only=True,
                                     default='')

    class Meta:
        model = SeuilReapproCasier
        fields = ['id', 'bin', 'bin_code', 'produit', 'seuil',
                  'quantite_cible', 'actif', 'created_at']
        read_only_fields = ['created_at']


class TacheReapproInterneSerializer(serializers.ModelSerializer):
    bin_cible_code = serializers.CharField(source='bin_cible.code',
                                           read_only=True, default='')
    bin_source_code = serializers.CharField(source='bin_source.code',
                                            read_only=True, default='')

    class Meta:
        model = TacheReapproInterne
        fields = ['id', 'produit', 'bin_cible', 'bin_cible_code',
                  'bin_source', 'bin_source_code', 'quantite', 'statut',
                  'note', 'created_at']
        read_only_fields = ['note', 'created_at']


class SeuilReapproCasierViewSet(CompanyScopedModelViewSet):
    """Seuils de réappro par casier de picking. Poser un seuil, c'est
    DÉCLARER le casier comme casier de prélèvement."""
    queryset = SeuilReapproCasier.objects.select_related(
        'bin', 'produit').all()
    serializer_class = SeuilReapproCasierSerializer
    ordering = ['bin_id']

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
        if self.action in WRITE_ACTIONS:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs


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
