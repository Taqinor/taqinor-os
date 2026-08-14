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

from rest_framework.decorators import api_view, permission_classes

from authentication.permissions import (
    IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import (
    AccordRFAFournisseur, DeclarationConsommation, DepotConsignation,
)

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


# ═══════════════════════════════════════════════════════════════════════════
# NTDST5 — Remises arrière (RFA) fournisseurs
# ═══════════════════════════════════════════════════════════════════════════

class AccordRFAFournisseurSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(
        source='fournisseur.nom', read_only=True, default='')
    avoir_deja_genere = serializers.BooleanField(read_only=True)

    class Meta:
        model = AccordRFAFournisseur
        fields = [
            'id', 'fournisseur', 'fournisseur_nom', 'periode_debut',
            'periode_fin', 'seuil_ca_achat', 'taux_pct', 'montant_fixe',
            'statut', 'avoir_genere', 'avoir_deja_genere', 'note',
            'created_at',
        ]
        # L'avoir est posé par l'action dédiée, JAMAIS par un PATCH : sinon la
        # garde d'idempotence se contourne en une requête.
        read_only_fields = ['avoir_genere', 'avoir_deja_genere', 'created_at']

    def validate(self, attrs):
        taux = attrs.get('taux_pct', getattr(self.instance, 'taux_pct', None))
        fixe = attrs.get('montant_fixe',
                         getattr(self.instance, 'montant_fixe', None))
        if taux is None and fixe is None:
            raise serializers.ValidationError(
                'Renseignez soit un taux (%), soit un montant fixe.')
        if taux is not None and fixe is not None:
            raise serializers.ValidationError(
                'Taux et montant fixe sont exclusifs : choisissez-en un.')
        debut = attrs.get('periode_debut',
                          getattr(self.instance, 'periode_debut', None))
        fin = attrs.get('periode_fin',
                        getattr(self.instance, 'periode_fin', None))
        if debut and fin and fin < debut:
            raise serializers.ValidationError(
                'La fin de période doit suivre son début.')
        return attrs


class AccordRFAFournisseurViewSet(CompanyScopedModelViewSet):
    """NTDST5 — accords de remise arrière fournisseur.

    Montants d'ACHAT : lecture responsable/admin, jamais tout rôle.
    """
    queryset = AccordRFAFournisseur.objects.select_related(
        'fournisseur', 'avoir_genere').all()
    serializer_class = AccordRFAFournisseurSerializer
    ordering = ['-periode_debut', '-id']

    def get_permissions(self):
        if self.action in READ_ACTIONS + WRITE_ACTIONS + [
                'calcul', 'generer_avoir']:
            return [IsResponsableOrAdmin()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        fournisseur = self.request.query_params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    @extend_schema(responses={
        200: inline_serializer('StockRfaCalcul', {
            'accord_id': serializers.IntegerField(),
            'fournisseur_id': serializers.IntegerField(),
            'periode_debut': serializers.CharField(),
            'periode_fin': serializers.CharField(),
            'ca_achat': serializers.CharField(),
            'seuil_ca_achat': serializers.CharField(),
            'seuil_atteint': serializers.BooleanField(),
            'progression_pct': serializers.CharField(),
            'montant_du': serializers.CharField(),
            'avoir_deja_genere': serializers.BooleanField(),
        }),
    })
    @action(detail=True, methods=['get'], url_path='calcul',
            permission_classes=[IsResponsableOrAdmin])
    def calcul(self, request, pk=None):
        """CA d'achat réceptionné, progression vers le seuil et montant dû."""
        from ..services_rfa import calculer_rfa_fournisseur
        return Response(calculer_rfa_fournisseur(self.get_object()))

    @extend_schema(request=None, responses={
        201: inline_serializer('StockRfaAvoirGenere', {
            'avoir_id': serializers.IntegerField(),
            'reference': serializers.CharField(),
            'montant_ttc': serializers.CharField(),
        }),
    })
    @action(detail=True, methods=['post'], url_path='generer-avoir',
            permission_classes=[IsResponsableOrAdmin])
    def generer_avoir(self, request, pk=None):
        """Matérialise la remise due en AVOIR fournisseur — UNE SEULE FOIS
        par accord (deuxième appel refusé)."""
        from ..services_rfa import generer_avoir_rfa

        accord = self.get_object()
        try:
            avoir = generer_avoir_rfa(accord, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'avoir_id': avoir.id, 'reference': avoir.reference,
            'montant_ttc': str(avoir.montant_ttc),
        }, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════════════════════
# NTDST10 — Disponibilité ATP / NTDST18 — Catalogue B2B temps réel
# ═══════════════════════════════════════════════════════════════════════════

ATP_SHAPE = {
    'produit': serializers.IntegerField(),
    'disponible_maintenant': serializers.IntegerField(),
    'quantite_reservee': serializers.IntegerField(),
    'disponible_le': serializers.CharField(allow_null=True),
    'quantite_a_cette_date': serializers.IntegerField(),
    'emplacement': serializers.IntegerField(allow_null=True),
}


class AtpProduitMixin:
    """NTDST10 — ``produits/{id}/atp/`` monté sur le viewset produit."""

    @extend_schema(responses={
        200: inline_serializer('StockProduitAtp', ATP_SHAPE)})
    @action(detail=True, methods=['get'], url_path='atp',
            permission_classes=[IsAnyRole])
    def atp(self, request, pk=None):
        """Disponibilité DATÉE : combien MAINTENANT, et à partir de QUAND.

        Un produit en rupture avec une commande fournisseur confirmée dans 5
        jours renvoie ``disponible_le`` = cette date. Lecture seule, aucun
        prix, aucun coût.
        """
        from ..selectors_negoce import atp_produit
        return Response(atp_produit(request.user.company, self.get_object()))


@extend_schema(responses={
    200: inline_serializer('StockCatalogueB2b', {
        'client': serializers.IntegerField(allow_null=True),
        'total': serializers.IntegerField(),
        'limite': serializers.IntegerField(),
        'offset': serializers.IntegerField(),
        'produits': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET'])
@permission_classes([IsAnyRole])
def catalogue_b2b_view(request):
    """NTDST18 — catalogue produit résolu POUR UN CLIENT
    (``?client=&categorie=&marque=&q=&limite=&offset=``).

    Prix appliqué via les listes de prix du client (XSAL1/XSAL2), ATP
    (NTDST10), image produit. ``prix_achat`` n'y figure JAMAIS : cette donnée
    alimente le futur portail client (NTPRT).
    """
    # Lecture cross-app par le SELECTOR de `crm` — jamais un import de ses
    # modèles (frontière inter-apps).
    from apps.crm.selectors import get_company_client

    from ..selectors_negoce import catalogue_b2b

    company = request.user.company
    client = None
    client_id = request.query_params.get('client')
    if client_id:
        client = get_company_client(company, client_id)
        if client is None:
            return Response({'detail': 'Client introuvable dans cette '
                                       'société.'},
                            status=status.HTTP_404_NOT_FOUND)
    return Response(catalogue_b2b(
        company, client,
        categorie=request.query_params.get('categorie'),
        marque=request.query_params.get('marque'),
        recherche=request.query_params.get('q') or '',
        limite=request.query_params.get('limite') or 50,
        offset=request.query_params.get('offset') or 0))


# ═══════════════════════════════════════════════════════════════════════════
# NTDST14 — Van sales : stock embarqué véhicule
# ═══════════════════════════════════════════════════════════════════════════

@extend_schema(request=None, responses={
    200: inline_serializer('StockVehiculeEmbarque', {
        'actif_flotte': serializers.IntegerField(),
        'lignes': serializers.ListField(child=serializers.DictField()),
    }),
})
@api_view(['GET', 'POST'])
@permission_classes([IsResponsableOrAdmin])
def stock_embarque_view(request, actif_flotte_id):
    """NTDST14 — GET le contenu d'un véhicule ; POST charge ou décharge.

    Corps du POST : ``{operation: 'charger'|'decharger',
    lignes: [{produit, quantite}]}``. Charger décrémente le dépôt principal
    et n'affecte AUCUN autre emplacement ; décharger fait l'inverse pour le
    reliquat non vendu.
    """
    from ..services_van_sales import (
        charger_vehicule, decharger_vehicule, stock_embarque, van_sales_active,
    )

    company = request.user.company
    if not van_sales_active(company):
        return module_desactive('van sales')

    if request.method == 'POST':
        operation = (request.data.get('operation') or '').strip()
        lignes = request.data.get('lignes')
        action_service = {
            'charger': charger_vehicule, 'decharger': decharger_vehicule,
        }.get(operation)
        if action_service is None:
            return Response(
                {'detail': "Opération invalide : attendu « charger » ou "
                           '« decharger ».'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            action_service(company=company, user=request.user,
                           actif_flotte_id=actif_flotte_id, lignes=lignes)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'actif_flotte': int(actif_flotte_id),
        'lignes': stock_embarque(company, actif_flotte_id),
    })
