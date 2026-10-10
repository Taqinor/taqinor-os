from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.parsers import JSONParser
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from authentication.mixins import TenantMixin
from rest_framework import serializers
from ..openapi_helpers import INT, LISTE, P, STR, corps
from ..models import LotEntrepot
from ..serializers import LotEntrepotSerializer
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

READ_ACTIONS = ['list', 'retrieve']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


@extend_schema_view(list=extend_schema(parameters=[P('produit', INT), P('avec_stock', STR, False, 'Seulement les lots avec stock restant')]))
class LotEntrepotViewSet(TenantMixin, viewsets.ReadOnlyModelViewSet):
    """XSTK6 — registre de LOTS en entrepôt (miroir de `SerieEntrepot`
    FG323). LECTURE SEULE : alimenté à la confirmation d'une réception,
    décrémenté uniquement via l'action `sortir` (garde du stock périmé,
    FEFO). Jamais d'écriture libre du restant depuis le corps de la requête.
    """
    queryset = LotEntrepot.objects.select_related(
        'produit', 'emplacement').all()
    serializer_class = LotEntrepotSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['numero_lot', 'produit__nom', 'reference_reception']
    ordering_fields = ['date_peremption', 'date_creation', 'quantite_restante']
    ordering = ['date_peremption', '-date_creation']

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['fefo']:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        seulement_restant = self.request.query_params.get('avec_stock')
        if seulement_restant:
            qs = qs.filter(quantite_restante__gt=0)
        return qs

    @extend_schema(parameters=[P('produit', INT, True, 'Produit (id)'), P('quantite', INT, False, 'Quantité (défaut 1)')], responses=LISTE)
    @action(detail=False, methods=['get'], url_path='fefo',
            permission_classes=[IsAnyRole])
    def fefo(self, request):
        """XSTK6 — suggestion FEFO (péremption la plus proche d'abord) pour
        sortir ``quantite`` unités d'un produit. Query params : ``produit``
        (id, requis), ``quantite`` (int, défaut 1). LECTURE SEULE."""
        produit_id = request.query_params.get('produit')
        if not produit_id:
            return Response(
                {'detail': 'Le paramètre « produit » est requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            quantite = int(request.query_params.get('quantite', 1))
        except (TypeError, ValueError):
            quantite = 1
        from ..models import Produit
        produit = Produit.objects.filter(
            company=request.user.company, id=produit_id).first()
        if produit is None:
            return Response(
                {'detail': 'Produit introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        from ..services import suggestion_fefo
        plan = suggestion_fefo(request.user.company, produit, quantite)
        return Response([
            {
                'lot_id': p['lot'].id,
                'numero_lot': p['lot'].numero_lot,
                'date_peremption': p['lot'].date_peremption,
                'quantite': p['quantite'],
            }
            for p in plan
        ])

    @extend_schema(request=corps('LotSortirCorps', quantite=serializers.IntegerField(), forcer=serializers.BooleanField(required=False), motif=serializers.CharField(required=False, allow_blank=True)), responses=LotEntrepotSerializer)
    @action(detail=True, methods=['post'], url_path='sortir')
    def sortir(self, request, pk=None):
        """XSTK6 — sort une quantité de CE lot. Bloque un lot périmé (garde
        société, défaut ON) sauf ``{"forcer": true, "motif": "..."}`` tracé.
        """
        lot = self.get_object()
        try:
            quantite = int(request.data.get('quantite'))
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Quantité invalide.'},
                status=status.HTTP_400_BAD_REQUEST)
        from django.db import transaction
        from ..models import MouvementStock, Produit
        from ..services import record_stock_movement, sortir_lot_entrepot
        company = request.user.company
        try:
            # ASTK204 — le lot ET le stock du produit bougent ensemble, dans
            # UNE transaction : une SORTIE tracée (record_stock_movement,
            # référence = numéro du lot), produit verrouillé avant lecture.
            with transaction.atomic():
                produit = Produit.objects.select_for_update().get(
                    pk=lot.produit_id, company=company)
                avant = produit.quantite_stock
                if quantite > avant:
                    raise ValueError(
                        f'Stock insuffisant pour {produit.nom} '
                        f'({avant} en stock).')
                sortir_lot_entrepot(
                    company=company, lot=lot, quantite=quantite,
                    user=request.user,
                    forcer=bool(request.data.get('forcer')),
                    motif=request.data.get('motif'))
                motif = request.data.get('motif')
                record_stock_movement(
                    company=company, produit=produit,
                    type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                    quantite=quantite, quantite_avant=avant,
                    quantite_apres=avant - quantite,
                    reference=lot.numero_lot,
                    note=(f'Sortie du lot {lot.numero_lot}'
                          + (f' — motif : {motif}' if motif else '')),
                    created_by=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(lot).data)
