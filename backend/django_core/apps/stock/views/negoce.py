"""Groupe NTDST — vues NÉGOCE : consignation, paramètres, van sales, RFA.

GARDE MODULAIRE (NTDST31). Quand ``ParametresNegoce.consignation_activee`` ou
``van_sales_active`` est faux, les endpoints correspondants renvoient un **403
explicite** — pas seulement une entrée de menu cachée côté UI. Un admin est
refusé comme les autres : c'est une fonctionnalité DÉSACTIVÉE, pas un droit
manquant.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import DeclarationConsommation, DepotConsignation

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


def module_desactive(nom):
    """403 explicite d'un module négoce éteint (NTDST31)."""
    return Response(
        {'detail': f'Le module « {nom} » est désactivé pour cette société '
                   f'(Paramètres → Négoce).'},
        status=status.HTTP_403_FORBIDDEN)


class DeclarationConsommationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeclarationConsommation
        fields = ['id', 'depot', 'quantite', 'date_declaration', 'statut',
                  'document_reference', 'note', 'created_at']
        read_only_fields = ['statut', 'document_reference', 'created_at']


class DepotConsignationSerializer(serializers.ModelSerializer):
    quantite_restante = serializers.IntegerField(read_only=True)
    produit_nom = serializers.CharField(
        source='produit.nom', read_only=True, default='')
    declarations = DeclarationConsommationSerializer(
        many=True, read_only=True)

    class Meta:
        model = DepotConsignation
        fields = [
            'id', 'client', 'produit', 'produit_nom', 'quantite_deposee',
            'quantite_consommee_declaree', 'quantite_restante', 'date_depot',
            'adresse_site', 'statut', 'emplacement_source', 'note',
            'declarations', 'created_at',
        ]
        # Les quantités consommées et le statut évoluent UNIQUEMENT par les
        # services (jamais par un PATCH direct : ce serait le double décrément).
        read_only_fields = [
            'quantite_consommee_declaree', 'quantite_restante', 'statut',
            'created_at',
        ]


class DepotConsignationViewSet(CompanyScopedModelViewSet):
    """NTDST3 — dépôts de consignation chez les clients.

    La CRÉATION passe par le service (sortie de stock motivée, sans facture) ;
    la consommation par l'action dédiée. Aucune de ces deux quantités n'est
    modifiable par un PATCH.
    """
    queryset = DepotConsignation.objects.select_related(
        'produit', 'client').prefetch_related('declarations').all()
    serializer_class = DepotConsignationSerializer
    ordering = ['-date_depot', '-id']

    def get_permissions(self):
        # `get_permissions` prime sur le `permission_classes` d'une @action :
        # chaque action est listée explicitement ici.
        if self.action in READ_ACTIONS + ['releve', 'releve_pdf']:
            return [IsAnyRole()]
        if self.action in WRITE_ACTIONS + ['declarer_consommation',
                                           'export_xlsx']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        # Filtrage MANUEL (aucun DjangoFilterBackend branché ici).
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        client = params.get('client')
        if client:
            qs = qs.filter(client_id=client)
        return qs

    def initial(self, request, *args, **kwargs):
        """NTDST31 — refuse TOUTE la ressource quand le module est éteint."""
        super().initial(request, *args, **kwargs)
        from ..services_consignation import consignation_activee
        company = getattr(request.user, 'company', None)
        if company is not None and not consignation_activee(company):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                'Le module « consignation » est désactivé pour cette société '
                '(Paramètres → Négoce).')

    def create(self, request, *args, **kwargs):
        from ..services_consignation import creer_depot_consignation

        try:
            depot = creer_depot_consignation(
                company=request.user.company, user=request.user,
                client_id=request.data.get('client'),
                produit_id=request.data.get('produit'),
                quantite=request.data.get('quantite_deposee'),
                date_depot=request.data.get('date_depot'),
                adresse_site=request.data.get('adresse_site') or '',
                emplacement_id=request.data.get('emplacement_source'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(depot).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None,
                   responses={201: DeclarationConsommationSerializer})
    @action(detail=True, methods=['post'], url_path='declarer-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def declarer_consommation(self, request, pk=None):
        """NTDST3 — le client déclare ce qu'il a consommé.

        Ne retouche JAMAIS le stock : la marchandise est partie du dépôt à la
        mise en consignation. Refuse une quantité négative ou supérieure au
        restant."""
        from ..services_consignation import declarer_consommation

        depot = self.get_object()
        try:
            declaration = declarer_consommation(
                depot=depot, user=request.user,
                quantite=request.data.get('quantite'),
                date_declaration=request.data.get('date_declaration'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(DeclarationConsommationSerializer(declaration).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses={
        200: inline_serializer('StockReleveConsignation', {
            'depot_id': serializers.IntegerField(),
            'client_id': serializers.IntegerField(),
            'produit_id': serializers.IntegerField(),
            'produit_nom': serializers.CharField(allow_blank=True),
            'date_depot': serializers.CharField(),
            'adresse_site': serializers.CharField(allow_blank=True),
            'statut': serializers.CharField(),
            'quantite_deposee': serializers.IntegerField(),
            'quantite_consommee': serializers.IntegerField(),
            'quantite_facturee': serializers.IntegerField(),
            'quantite_restante': serializers.IntegerField(),
            'declarations': serializers.ListField(
                child=serializers.DictField()),
        }),
    })
    @action(detail=True, methods=['get'], url_path='releve',
            permission_classes=[IsAnyRole])
    def releve(self, request, pk=None):
        """Relevé cumulé : déposé / consommé / facturé / restant."""
        from ..services_consignation import releve_consignation
        return Response(releve_consignation(self.get_object()))
