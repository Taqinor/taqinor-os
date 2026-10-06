from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet  # noqa: F401
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import (  # noqa: F401
    Produit, Categorie, Fournisseur, MouvementStock, Marque,
    BonCommandeFournisseur, EmplacementStock, TransfertStock, PrixFournisseur,
    RetourFournisseur, ReceptionFournisseur, FactureFournisseur,
    PaiementFournisseur,
)
from ..serializers import (  # noqa: F401
    ProduitSerializer,
    CategorieSerializer,
    FournisseurSerializer,
    MouvementStockSerializer,
    MarqueSerializer,
    BonCommandeFournisseurSerializer,
    EmplacementStockSerializer,
    TransfertStockSerializer,
    PrixFournisseurSerializer,
    RetourFournisseurSerializer,
    ReceptionFournisseurSerializer,
    FactureFournisseurSerializer,
    PaiementFournisseurSerializer,
)
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class MouvementStockViewSet(CompanyScopedModelViewSet):
    # ARC4 — sweep : base transverse unique (TenantMixin + ModelViewSet, via
    # CompanyScopedModelViewSet). get_queryset AJOUTE le garde-fou
    # produit__company (belt-and-braces contre une référence produit
    # inter-société) par-dessus le scoping société de la base — comportement
    # inchangé.
    queryset = MouvementStock.objects.select_related(
        'produit', 'created_by'
    ).all()
    serializer_class = MouvementStockSerializer
    # ASTK28 — registre APPEND-ONLY par l'API comme par l'admin (AUD215) :
    # un mouvement posé ne se modifie ni ne se supprime (PUT/PATCH/DELETE →
    # 405) ; une erreur se corrige par un mouvement inverse. Même patron que
    # MouvementRebutViewSet (views/wms.py).
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['produit__nom', 'reference', 'note']
    ordering_fields = ['date', 'type_mouvement', 'quantite']
    ordering = ['-date']

    def get_permissions(self):
        if self.action in READ_ACTIONS + ['export_xlsx', 'agregation']:
            return [IsAnyRole()]
        elif self.action == 'create':
            return [HasPermissionOrLegacy('stock_mouvement')()]
        else:
            return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            # produit__company belt-and-braces guard against cross-tenant
            # produit references slipping in (company= is already applied by
            # the base — this narrows further, never re-widens).
            qs = qs.filter(produit__company=user.company)
        # FG60 — Filtres supplémentaires
        params = self.request.query_params
        type_mv = params.get('type_mouvement')
        if type_mv:
            qs = qs.filter(type_mouvement=type_mv)
        produit_id = params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        date_min = params.get('date_min')
        if date_min:
            qs = qs.filter(date__date__gte=date_min)
        date_max = params.get('date_max')
        if date_max:
            qs = qs.filter(date__date__lte=date_max)
        return qs

    @action(detail=False, methods=['post'], url_path='export-xlsx',
            permission_classes=[IsAnyRole])
    def export_xlsx(self, request):
        """FG60 — Export Excel de la liste des mouvements de stock (INTERNE).
        Prix d'achat jamais inclus."""
        from ..services import export_mouvements_xlsx
        qs = self.filter_queryset(self.get_queryset())
        return export_mouvements_xlsx(request.user.company, qs)

    @action(detail=False, methods=['get'], url_path='agregation',
            permission_classes=[IsAnyRole])
    def agregation(self, request):
        """ZSTK7 — « Reporting ▸ Moves History » : quantités entrées/sorties/
        nettes agrégées par produit/type/mois/emplacement sur une période.
        INTERNE. ``?export=xlsx`` télécharge le même agrégat (jamais
        ``?format=``, réservé au routage DRF)."""
        from ..selectors import mouvements_agreges

        group_by = request.query_params.get('group_by', 'produit')
        try:
            rows = mouvements_agreges(
                request.user.company, group_by=group_by,
                date_min=request.query_params.get('date_min'),
                date_max=request.query_params.get('date_max'))
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if request.query_params.get('export') == 'xlsx':
            from apps.records.xlsx import build_xlsx_response
            headers = ['Groupe', 'Entrées', 'Sorties', 'Net']
            xlsx_rows = [
                [r['libelle'], r['entrees'], r['sorties'], r['net']]
                for r in rows]
            return build_xlsx_response(
                'mouvements-agregation.xlsx', headers, xlsx_rows,
                sheet_title='Agrégation mouvements')
        return Response(rows)

    #: ASTK34 — types qui ont leur PROPRE chemin (contrôles, emplacements,
    #: motif) et ne se posent donc jamais par cette route générique.
    TYPES_REFUSES = {
        MouvementStock.TypeMouvement.TRANSFERT: (
            'Un transfert se fait depuis les transferts de stock '
            '(source et destination), pas par un mouvement libre.'),
        MouvementStock.TypeMouvement.REBUT: (
            'Un rebut se déclare par la déclaration de rebut (motif '
            'obligatoire), pas par un mouvement libre.'),
    }

    def perform_create(self, serializer):
        """ASTK34 — tout mouvement saisi passe par ``record_stock_movement``
        (service unique : registre, ``quantite_stock``, alerte seuil XSTK23,
        événement ``mouvement_stock_enregistre`` du miroir comptable).

        Sémantique de ``quantite`` conservée côté écran : ENTREE/SORTIE = une
        quantité ; AJUSTEMENT = le NIVEAU visé, converti ici en écart signé
        (le mouvement porte ``quantite`` = |écart|, avant → après)."""
        from rest_framework.exceptions import ValidationError
        from ..services import record_stock_movement
        donnees = serializer.validated_data
        # ASTK5 — le produit d'une autre société est refusé dès la résolution
        # du champ (sérialiseur borné société : « objet inexistant »).
        produit = donnees['produit']
        user = self.request.user
        qte = donnees['quantite']
        type_mv = donnees['type_mouvement']
        if type_mv in self.TYPES_REFUSES:
            raise ValidationError(
                {'type_mouvement': self.TYPES_REFUSES[type_mv]})
        # ERR10 — la quantité d'une ENTREE/SORTIE doit être strictement
        # positive : on n'accepte ni 0, ni négatif (un négatif transformerait
        # silencieusement une SORTIE en augmentation de stock — corruption /
        # fraude).
        if type_mv in (
            MouvementStock.TypeMouvement.ENTREE,
            MouvementStock.TypeMouvement.SORTIE,
        ) and (qte is None or qte <= 0):
            raise ValidationError(
                {'quantite': 'La quantité doit être strictement positive.'})
        if (type_mv == MouvementStock.TypeMouvement.AJUSTEMENT
                and (qte is None or qte < 0)):
            raise ValidationError(
                {'quantite': 'Le niveau de stock visé ne peut pas être '
                             'négatif.'})
        # ERR23 — section critique atomique + verrou de ligne produit pour que
        # des SORTIEs concurrentes ne perdent pas de mise à jour et ne
        # corrompent pas les colonnes d'audit quantite_avant/quantite_apres.
        with transaction.atomic():
            produit = (Produit.objects.select_for_update()
                       .get(pk=produit.pk))
            qte_avant = produit.quantite_stock
            if type_mv == MouvementStock.TypeMouvement.ENTREE:
                qte_apres = qte_avant + qte
                quantite = qte
            elif type_mv == MouvementStock.TypeMouvement.SORTIE:
                qte_apres = qte_avant - qte
                quantite = qte
                # ERR10 — une SORTIE ne peut jamais faire descendre le stock
                # sous zéro (garde plancher) : refus explicite en 400.
                if qte_apres < 0:
                    raise ValidationError(
                        {'quantite': (
                            'Stock insuffisant : la sortie dépasse le stock '
                            f'disponible ({qte_avant}).')})
            else:
                # AJUSTEMENT — niveau visé → écart signé.
                qte_apres = qte
                quantite = abs(qte_apres - qte_avant)
                if quantite == 0:
                    raise ValidationError(
                        {'quantite': (
                            'Le niveau saisi est déjà le stock actuel '
                            f'({qte_avant}) : aucun ajustement à poser.')})
            mouvement = record_stock_movement(
                company=produit.company, produit=produit,
                type_mouvement=type_mv, quantite=quantite,
                quantite_avant=qte_avant, quantite_apres=qte_apres,
                reference=donnees.get('reference'),
                note=donnees.get('note'), created_by=user,
                bin_source=donnees.get('bin_source'),
                bin_destination=donnees.get('bin_destination'))
            unite = donnees.get('unite_logistique')
            if unite is not None:
                # Colonne descriptive du mouvement qui vient d'être posé (le
                # service ne la porte pas) : jamais une quantité.
                MouvementStock.objects.filter(pk=mouvement.pk).update(
                    unite_logistique=unite)
                mouvement.unite_logistique = unite
        serializer.instance = mouvement
