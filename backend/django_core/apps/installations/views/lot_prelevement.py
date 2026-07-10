"""Vues ZSTK10 — regroupement de prélèvements en lot (batch transfer).

``LotPrelevementViewSet`` : à la création, groupe une sélection de
pick-lists (``pick_list_ids`` dans le corps) du MÊME dépôt
(``services.creer_lot_prelevement``). Action ``lignes`` : vue consolidée
triée par casier. Action ``cocher-ligne`` : coche une ligne, propage à la
pick-list source. Action ``cloturer`` : clôture le lot si toutes les
pick-lists sont soldées. Lecture tout rôle, écriture responsable/admin.
Multi-tenant via ``TenantMixin``."""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import LotPrelevement
from ..serializers import LotPrelevementSerializer
from .. import services

READ_ACTIONS = ['list', 'retrieve']


class LotPrelevementViewSet(CompanyScopedModelViewSet):
    """ZSTK10 — lots de prélèvement. Lecture tout rôle, écriture
    responsable/admin. Société/`created_by`/référence posés serveur ; les
    pick-lists sont fournies via `pick_list_ids` dans le corps à la
    création."""
    queryset = LotPrelevement.objects.select_related(
        'operateur', 'created_by').prefetch_related('pick_lists').all()
    serializer_class = LotPrelevementSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        company = request.user.company
        pick_list_ids = request.data.get('pick_list_ids') or []
        try:
            lot = services.creer_lot_prelevement(
                company, pick_list_ids, request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(lot).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['get'])
    def lignes(self, request, pk=None):
        """ZSTK10 — vue consolidée des lignes de TOUTES les pick-lists du
        lot, triées par casier (`BinLocation.ordre`)."""
        lot = self.get_object()
        return Response(services.lignes_lot_prelevement(lot))

    @action(detail=True, methods=['post'], url_path='cocher-ligne')
    def cocher_ligne(self, request, pk=None):
        """ZSTK10 — coche une ligne du lot (`ligne_id` dans le corps),
        propage à la `PickListLigne` source."""
        lot = self.get_object()
        ligne_id = request.data.get('ligne_id')
        quantite = request.data.get('quantite_prelevee')
        if not ligne_id:
            raise ValidationError({'ligne_id': 'Ce champ est requis.'})
        try:
            services.cocher_ligne_lot(lot, ligne_id, quantite_prelevee=quantite)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(services.lignes_lot_prelevement(lot))

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """ZSTK10 — clôture le lot (uniquement si toutes ses pick-lists sont
        soldées)."""
        lot = self.get_object()
        try:
            services.cloturer_lot_prelevement(lot)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(lot).data)
