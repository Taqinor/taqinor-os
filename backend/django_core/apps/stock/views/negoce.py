"""Groupe NTDST — vues NÉGOCE : consignation, paramètres, RFA.

GARDE MODULAIRE (NTDST31). Quand ``ParametresNegoce.consignation_activee``
est faux, les endpoints correspondants renvoient un **403 explicite** — pas
seulement une entrée de menu cachée côté UI. Un admin est refusé comme les
autres : c'est une fonctionnalité DÉSACTIVÉE, pas un droit manquant.
"""
from drf_spectacular.utils import (
    extend_schema, extend_schema_field, extend_schema_view, inline_serializer,
)
from rest_framework.parsers import JSONParser
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework.decorators import api_view, parser_classes, permission_classes

from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminRole, IsAnyRole, IsResponsableOrAdmin,
)
from core.serializers import CompanyScopedRelationsMixin
from ..openapi_helpers import (  # noqa: F401
    INT, P, S, STR, corps,
)
from core.viewsets import CompanyScopedModelViewSet

from ..models import (
    AccordRFAFournisseur, DeclarationConsommation, DepotConsignation,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class DeclarationConsommationSerializer(CompanyScopedRelationsMixin,
                                        serializers.ModelSerializer):
    class Meta:
        model = DeclarationConsommation
        fields = ['id', 'depot', 'quantite', 'date_declaration', 'statut',
                  'document_reference', 'note', 'created_at']
        read_only_fields = ['statut', 'document_reference', 'created_at']


class DeclarationFactureeSerializer(DeclarationConsommationSerializer):
    """ASTK198 — réponse de ``declarer-consommation`` : la déclaration plus
    la facture BROUILLON créée (``facture_id`` / ``facture_reference``,
    contrat ``negoce_consignation_rfa.json`` ``exemple_nouveau_astk198``)."""
    facture_id = serializers.SerializerMethodField()
    facture_reference = serializers.SerializerMethodField()

    class Meta(DeclarationConsommationSerializer.Meta):
        fields = DeclarationConsommationSerializer.Meta.fields + [
            'facture_id', 'facture_reference']

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_facture_id(self, obj):
        facture = getattr(obj, 'facture', None)
        return facture.pk if facture is not None else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_facture_reference(self, obj):
        facture = getattr(obj, 'facture', None)
        return facture.reference if facture is not None else None


class DepotConsignationSerializer(CompanyScopedRelationsMixin,
                                  serializers.ModelSerializer):
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

    #: ASTK30 — champs FIGÉS après création : ils décrivent la marchandise
    #: réellement sortie du stock (1 mouvement CONSIGNATION posé à la
    #: création). Les modifier par un PATCH désaccorderait le dépôt de son
    #: mouvement (50 en dépôt pour 10 sortis).
    CHAMPS_FIGES = (
        'quantite_deposee', 'produit', 'client', 'emplacement_source',
        'date_depot',
    )

    def validate(self, attrs):
        if self.instance is not None:
            figes = [nom for nom in self.CHAMPS_FIGES
                     if nom in getattr(self, 'initial_data', {})]
            if figes:
                raise serializers.ValidationError({
                    nom: ('Champ figé après la création du dépôt '
                          '(il décrit la marchandise réellement sortie).')
                    for nom in figes})
        return super().validate(attrs)


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR), P('client', INT)]))
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

    parser_classes = [JSONParser]

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

    def perform_destroy(self, instance):
        """ASTK30 — un dépôt qui porte encore des unités chez le client ne
        disparaît jamais sans mouvement : aucune action de restitution
        (ENTREE tracée) n'existe encore, donc la suppression est REFUSÉE tant
        que ``quantite_restante`` > 0."""
        if instance.quantite_restante > 0:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': (
                f'{instance.quantite_restante} unité(s) sont encore en dépôt '
                'chez le client : la suppression effacerait leur trace. '
                'Déclarez leur consommation (ou leur restitution) avant.')})
        super().perform_destroy(instance)

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

    @extend_schema(request=corps('DeclarerConsommationCorps', quantite=S.IntegerField(), date_declaration=S.DateField(required=False, allow_null=True), note=S.CharField(required=False, allow_blank=True)),
                   responses={201: DeclarationFactureeSerializer})
    @action(detail=True, methods=['post'], url_path='declarer-consommation',
            permission_classes=[IsResponsableOrAdmin])
    def declarer_consommation(self, request, pk=None):
        """NTDST3 — le client déclare ce qu'il a consommé ; ASTK198 : la
        déclaration est facturée (facture BROUILLON, ``facture_id`` /
        ``facture_reference`` dans la réponse).

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
        return Response(DeclarationFactureeSerializer(declaration).data,
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

    @extend_schema(responses={(200, 'application/pdf'): bytes})
    @action(detail=True, methods=['get'], url_path='releve-pdf',
            permission_classes=[IsAnyRole])
    def releve_pdf(self, request, pk=None):
        """NTDST24 — relevé imprimable remis AU CLIENT comme justificatif.

        Mouvements triés par date, solde restant en pied de tableau. Rendu par
        le WeasyPrint des documents internes — jamais le moteur de devis
        vendorisé (règle #4). En-tête white-label (profil de la société).
        """
        from django.http import HttpResponse

        from ..utils.pdf_consignation import generate_releve_consignation_pdf

        depot = self.get_object()
        pdf = generate_releve_consignation_pdf(depot)
        reponse = HttpResponse(pdf, content_type='application/pdf')
        reponse['Content-Disposition'] = (
            f'inline; filename="releve-consignation-{depot.id}.pdf"')
        return reponse

    @extend_schema(parameters=[P('statut', STR)], responses={
        (200, 'application/vnd.openxmlformats-officedocument.'
              'spreadsheetml.sheet'): bytes})
    @action(detail=False, methods=['get'], url_path='export-xlsx',
            permission_classes=[IsResponsableOrAdmin])
    def export_xlsx(self, request):
        """NTDST41 — export XLSX de TOUS les dépôts (``?statut=actif``).

        Destiné au contrôle physique périodique multi-sites. Le total
        « restant » de l'export est exactement la somme des restants des
        dépôts exportés (ligne de total en fin de feuille).
        """
        from apps.records.xlsx import build_xlsx_response

        depots = self.filter_queryset(self.get_queryset())
        statut = request.query_params.get('statut')
        if statut:
            depots = depots.filter(statut=statut)

        entetes = ['Client', 'Produit', 'SKU', 'Site', 'Déposé', 'Consommé',
                   'Restant', 'Dernière déclaration', 'Statut']
        lignes, total_restant = [], 0
        # APRF35 — la dernière déclaration de chaque dépôt est lue dans la
        # MÊME requête (sous-requête, même tri ``-date_declaration, -id``) :
        # avant, une requête par dépôt.
        from django.db.models import OuterRef, Subquery
        from ..models_consignation import DeclarationConsommation
        derniere_date = Subquery(
            DeclarationConsommation.objects.filter(depot=OuterRef('pk'))
            .order_by('-date_declaration', '-id')
            .values('date_declaration')[:1])
        for depot in depots.select_related('client', 'produit').annotate(
                derniere_declaration_date=derniere_date):
            derniere = depot.derniere_declaration_date
            total_restant += depot.quantite_restante
            # ASTK7 — défense en profondeur : un dépôt hérité qui pointe un
            # client d'une AUTRE société n'imprime jamais son nom.
            client_ok = getattr(depot.client, 'company_id', None) == (
                depot.company_id)
            lignes.append([
                (getattr(depot.client, 'nom', '') or '') if client_ok else '',
                getattr(depot.produit, 'nom', '') or '',
                getattr(depot.produit, 'sku', '') or '',
                depot.adresse_site,
                depot.quantite_deposee,
                depot.quantite_consommee_declaree,
                depot.quantite_restante,
                (derniere.isoformat() if derniere else ''),
                depot.get_statut_display(),
            ])
        lignes.append(['TOTAL', '', '', '', '', '', total_restant, '', ''])
        return build_xlsx_response(
            'consignations.xlsx', entetes, lignes,
            sheet_title='Consignations')


# ═══════════════════════════════════════════════════════════════════════════
# NTDST5 — Remises arrière (RFA) fournisseurs
# ═══════════════════════════════════════════════════════════════════════════

class AccordRFAFournisseurSerializer(CompanyScopedRelationsMixin,
                                     serializers.ModelSerializer):
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


@extend_schema_view(list=extend_schema(parameters=[P('fournisseur', INT), P('statut', STR)]))
class AccordRFAFournisseurViewSet(CompanyScopedModelViewSet):
    """NTDST5 — accords de remise arrière fournisseur.

    Montants d'ACHAT : lecture responsable/admin, jamais tout rôle.
    """
    queryset = AccordRFAFournisseur.objects.select_related(
        'fournisseur', 'avoir_genere').all()
    serializer_class = AccordRFAFournisseurSerializer
    ordering = ['-periode_debut', '-id']

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action == 'generer_avoir':
            # ASTK19 (D-ASTK-3) — émettre l'avoir RFA = « payer ».
            return [HasPermissionOrLegacy('achats_payer')()]
        if self.action in READ_ACTIONS + WRITE_ACTIONS + ['calcul']:
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


@extend_schema(parameters=[P('client', INT), P('categorie', INT), P('marque', STR), P('q', STR), P('limite', INT), P('offset', INT)], responses={
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
# NTDST30 — Paramètres négoce par société (singleton)
# ═══════════════════════════════════════════════════════════════════════════

class ParametresNegoceSerializer(CompanyScopedRelationsMixin,
                                 serializers.ModelSerializer):
    class Meta:
        from ..models import ParametresNegoce as _ParametresNegoce

        model = _ParametresNegoce
        # ASTK201 (C-ASTK-049) — seuls les réglages RÉELLEMENT lus sont
        # exposés : `consignation_activee` (services_consignation) et
        # `atp_horizon_jours` (selectors_negoce). Les cinq autres colonnes
        # restent en base (aucune migration destructive) mais ne sont plus
        # servies ; les écrire → 400 « Réglage non branché. ».
        fields = [
            'id', 'consignation_activee', 'atp_horizon_jours', 'updated_at',
        ]
        # `company` n'est JAMAIS acceptée du corps : le singleton est résolu
        # depuis `request.user.company`.
        read_only_fields = ['updated_at']

    REGLAGES_NON_BRANCHES = (
        'van_sales_active', 'seuil_alerte_rfa_pct', 'heures_tournee_defaut',
        'seuil_alerte_marge_pct', 'cout_rupture_jour_mad',
    )

    def validate(self, attrs):
        initial = getattr(self, 'initial_data', None) or {}
        erreurs = {
            champ: ['Réglage non branché.']
            for champ in self.REGLAGES_NON_BRANCHES if champ in initial
        }
        if erreurs:
            raise serializers.ValidationError(erreurs)
        return attrs


@extend_schema(request=None, responses={200: ParametresNegoceSerializer})
@api_view(['GET', 'PATCH'])
@parser_classes([JSONParser])
@permission_classes([IsResponsableOrAdmin])
def parametres_negoce_view(request):
    """NTDST30 — réglages négoce de LA société (singleton, créé à la demande).

    ASTK201 : seuls ``consignation_activee`` et ``atp_horizon_jours`` sont
    exposés — ce sont les deux réglages réellement lus. Aucune alerte RFA
    n'est branchée sur ce singleton.
    """
    from ..models import ParametresNegoce

    params = ParametresNegoce.get(request.user.company)
    if request.method == 'PATCH':
        serializer = ParametresNegoceSerializer(
            params, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # `company` reste celle du singleton : jamais lue du corps.
        serializer.save(company=params.company)
        params.refresh_from_db()
    return Response(ParametresNegoceSerializer(params).data)
