"""FG66 / DC36 — Vue du kit / nomenclature (BOM) vendable.

Un kit est un en-tête + des composants (produits du catalogue). DC36 : le kit
ne porte aucun prix / marque / TVA propre ; l'action ``exploser`` le décompose
en lignes composant avec prix/TVA/marque LUS sur chaque ``Produit`` au vol.
Multi-tenant : querysets filtrés par société + ``company`` forcée côté serveur
(TenantMixin)."""
from drf_spectacular.utils import extend_schema, extend_schema_serializer, extend_schema_view
from rest_framework.parsers import JSONParser
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from ..openapi_helpers import BOOL, DATE, NUM, OBJET, P, DecimalSoupleStock, corps
from ..utils.params import ID_MAX, corps_objet, decimal_ou_400, id_corps, types_corps_ou_400
from ..serializers import RevisionKitSerializer
from core.viewsets import CompanyScopedModelViewSet
from authentication.permissions import (
    IsAnyRole, IsAdminRole, IsResponsableOrAdmin, HasPermissionOrLegacy,
)

from ..models import KitProduit
from ..serializers import KitComposantSerializer, KitProduitSerializer

# ENF11 — nom de composant OpenAPI distinct de celui d'`installations`
# (collision drf-spectacular « KitComposant »). Posé ICI et non par décorateur
# dans serializers.py (fichier-mur, C20 : aucune croissance nette).
extend_schema_serializer(component_name='KitProduitComposant')(KitComposantSerializer)

FACTEUR_MIN, FACTEUR_MAX = 0.0001, 1000
#: CI #997 fuzz (4) — ratio de remplacement : décimal STRICTEMENT positif (chaîne
#: ou nombre JSON, 4 décimales) ; le champ sert au schéma ET au contrôle.
RATIO_REMPLACEMENT = DecimalSoupleStock(
    max_digits=12, decimal_places=4, borne_min='0.0001', required=False, allow_null=True)
_BOOLEENS = ('1', '0', 'true', 'false', 'True', 'False')
READ_ACTIONS = ['list', 'retrieve', 'exploser', 'revisions',
                'composition_au', 'disponibilite']
WRITE_ACTIONS = ['create', 'update', 'partial_update', 'dupliquer',
                 'remplacer_composant']


@extend_schema_view(list=extend_schema(parameters=[P('avec_disponibilite', BOOL, False,
                                                     'Inclure la disponibilité potentielle')]),
                    retrieve=extend_schema(parameters=[P('avec_disponibilite', BOOL, False,
                                                         'Inclure la disponibilité potentielle')]))
class KitProduitViewSet(CompanyScopedModelViewSet):
    queryset = KitProduit.objects.all().prefetch_related('composants__produit')
    serializer_class = KitProduitSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'sku', 'description']
    ordering = ['nom']
    # YAPIC2 — whitelist explicite (jamais '__all__').
    ordering_fields = ['nom', 'sku']

    parser_classes = [JSONParser]

    def get_serializer_context(self):
        # ZMFG9 — `?avec_disponibilite=1` sur la liste/fiche enrichit chaque
        # kit de sa disponibilité multi-niveaux (kits assemblables + goulots).
        # OPT-IN : l'explosion récursive par kit a un coût — le comportement
        # par défaut de la liste reste strictement inchangé.
        context = super().get_serializer_context()
        valeurs = (self.request.query_params.getlist('avec_disponibilite')
                   if self.request else [])
        # ERR fuzz : drapeau déclaré booléen — toute autre valeur (``null``,
        # répétée…) était lue « non » en silence ; elle répond 400.
        if len(valeurs) > 1 or any(v not in _BOOLEENS for v in valeurs):
            raise ValidationError(
                {'avec_disponibilite': ['Booléen attendu (true/false).']})
        context['avec_disponibilite'] = bool(valeurs) and valeurs[0] in ('1', 'true', 'True')
        return context

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            # XMFG18 — `revisions` / `composition-au` sont LECTURE SEULE
            # (composition sans aucun prix), même garde que `exploser`.
            return [IsAnyRole()]
        elif self.action == 'structure':
            # XMFG5 — l'écran est accessible à tout rôle (disponibilité), le
            # coût/marge sont retirés de la réponse pour les rôles sans
            # accès responsable/admin (jamais client-facing).
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS:
            # XMFG18 — `dupliquer` EST une écriture (crée un kit) : même
            # garde que create/update.
            return [HasPermissionOrLegacy('stock_modifier')()]
        return [IsAdminRole()]

    @extend_schema(parameters=[P('quantite', NUM, False, 'Quantité de kits (défaut 1)')],
                   responses=corps('KitExploserReponse', kit_id=serializers.IntegerField(),
                                   kit_nom=serializers.CharField(), quantite_kit=serializers.FloatField(),
                                   lignes=serializers.ListField(child=serializers.DictField())))
    @action(detail=True, methods=['get'], url_path='exploser')
    def exploser(self, request, *args, **kwargs):
        """Explose le kit en lignes composant (param ``quantite`` ≥ 1, défaut 1).
        XMFG17 — traverse récursivement les sous-kits ; un cycle ou une
        profondeur excessive renvoie un 400 clair plutôt qu'une RecursionError.
        Prix / TVA / marque dérivés des produits (DC36). Le prix d'achat n'est
        jamais exposé."""
        from ..services import exploser_kit, KitCycleError
        kit = self.get_object()
        # ERR fuzz : ``quantite`` déclarée nombre — ``null`` (ou toute valeur
        # illisible) était lue « 1 » en silence ; elle répond 400.
        quantite = float(decimal_ou_400(request.query_params.get('quantite'), 'quantite', 1))
        if quantite <= 0:
            quantite = 1
        try:
            lignes = exploser_kit(kit, quantite)
        except (KitCycleError, ValueError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'kit_id': kit.id,
            'kit_nom': kit.nom,
            'quantite_kit': quantite,
            'lignes': lignes,
        })

    @extend_schema(responses=OBJET)
    @action(detail=True, methods=['get'], url_path='structure')
    def structure(self, request, *args, **kwargs):
        """XMFG5 — nomenclature indentée + disponibilité + kits assemblables.
        XMFG17 — traverse récursivement les sous-kits (chaque ligne porte
        `niveau`) ; un cycle ou une profondeur excessive renvoie un 400 clair.
        Coût/marge RÉSERVÉS responsable/admin — retirés de la réponse pour
        les autres rôles (jamais client-facing)."""
        from ..services import structure_kit, KitCycleError
        kit = self.get_object()
        try:
            data = structure_kit(kit)
        except (KitCycleError, ValueError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        peut_voir_cout = IsResponsableOrAdmin().has_permission(request, self)
        if not peut_voir_cout:
            for ligne in data['composants']:
                ligne.pop('cout_unitaire', None)
                ligne.pop('cout_total', None)
            data.pop('cout_total_roll_up', None)
            data.pop('marge', None)
        else:
            # Le contrat d'API expose ces montants roll-up en CHAÎNE à 2
            # décimales ('9500.00') ; un Decimal brut serait rendu en nombre
            # JSON (9500.0). On les formate explicitement à la frontière vue.
            for _cle in ('cout_total_roll_up', 'marge'):
                if data.get(_cle) is not None:
                    data[_cle] = f'{data[_cle]:.2f}'
        return Response(data)

    @extend_schema(responses=RevisionKitSerializer(many=True))
    @action(detail=True, methods=['get'], url_path='revisions',
            pagination_class=None)
    def revisions(self, request, *args, **kwargs):
        """XMFG18 — historique des révisions de nomenclature de ce kit
        (numéro, date, utilisateur, snapshot JSON — sans aucun prix).
        Lecture seule."""
        from ..serializers import RevisionKitSerializer
        kit = self.get_object()
        qs = kit.revisions.select_related('user').order_by('-numero')
        return Response(RevisionKitSerializer(qs, many=True).data)

    @extend_schema(parameters=[P('date', DATE, True, 'Date (AAAA-MM-JJ)')], responses=RevisionKitSerializer)
    @action(detail=True, methods=['get'], url_path='composition-au')
    def composition_au(self, request, *args, **kwargs):
        """XMFG18 — « composition au JJ/MM/AAAA » : renvoie la révision en
        vigueur à la date donnée (`?date=JJ/MM/AAAA` ou `AAAA-MM-JJ`).
        404 si aucune révision n'existait encore à cette date."""
        from datetime import datetime
        from ..serializers import RevisionKitSerializer
        kit = self.get_object()
        brut = (request.query_params.get('date') or '').strip()
        date_limite = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
            try:
                date_limite = datetime.strptime(brut, fmt).date()
                break
            except ValueError:
                continue
        if date_limite is None:
            return Response(
                {'detail': 'Paramètre date requis (JJ/MM/AAAA ou '
                           'AAAA-MM-JJ).'},
                status=status.HTTP_400_BAD_REQUEST)
        from ..services import composition_kit_au
        revision = composition_kit_au(kit, date_limite)
        if revision is None:
            return Response(
                {'detail': 'Aucune révision à cette date.'},
                status=status.HTTP_404_NOT_FOUND)
        return Response(RevisionKitSerializer(revision).data)

    @extend_schema(responses=OBJET)
    @action(detail=True, methods=['get'], url_path='disponibilite')
    def disponibilite(self, request, *args, **kwargs):
        """ZMFG9 — disponibilité multi-niveaux du kit : nombre de kits
        COMPLETS assemblables avec le stock disponible (explosion récursive,
        stock partagé entre sous-kits jamais compté deux fois) + composants
        limitants (goulots). Un cycle renvoie 400 clair. Lecture seule."""
        from ..selectors import disponibilite_potentielle_recursive
        from ..services import KitCycleError
        kit = self.get_object()
        try:
            data = disponibilite_potentielle_recursive(
                kit, request.user.company)
        except (KitCycleError, ValueError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)

    # ERR fuzz : nombre JSON borné (l'écran envoie ``Number(...)``) — le décimal-
    # chaîne publié admettait « 0 », refusé ensuite (« rejected schema-compliant »).
    @extend_schema(request=corps('KitDupliquerCorps', facteur_echelle=serializers.FloatField(
        min_value=FACTEUR_MIN, max_value=FACTEUR_MAX, required=False, allow_null=True)),
                   responses={201: KitProduitSerializer})
    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, *args, **kwargs):
        """XMFG18 — duplique ce kit (en-tête + composants), avec facteur
        d'échelle optionnel sur les quantités (`facteur_echelle`, ex. 1.67 —
        arrondi propre). La copie reçoit sa révision n°1."""
        from ..services import dupliquer_kit
        kit = self.get_object()
        facteur = corps_objet(request).get('facteur_echelle')
        if facteur is not None and (isinstance(facteur, bool) or not isinstance(facteur, (int, float))):
            return Response({'detail': "Facteur d'échelle invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if facteur is not None and (0 < facteur < FACTEUR_MIN or facteur > FACTEUR_MAX):
            return Response({'detail': "Facteur d'échelle hors bornes (0,0001 à 1000)."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            copie = dupliquer_kit(
                kit, user=request.user, facteur_echelle=facteur)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(copie).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=corps('KitRemplacerComposantCorps',
                                 produit_ancien=serializers.IntegerField(min_value=1, max_value=ID_MAX),
                                 produit_nouveau=serializers.IntegerField(min_value=1, max_value=ID_MAX),
                                 ratio_quantite=RATIO_REMPLACEMENT,
                                 dry_run=serializers.BooleanField(required=False)), responses=OBJET)
    @action(detail=False, methods=['post'], url_path='remplacer-composant')
    def remplacer_composant(self, request):
        """XMFG19 — remplacement de MASSE d'un composant dans toutes les
        nomenclatures de la société (kits stock + kits de pré-assemblage
        installations). Body : `produit_ancien`, `produit_nouveau`,
        `ratio_quantite` (optionnel), `dry_run` (défaut true = préview).
        L'application (dry_run=false) est ATOMIQUE ; chaque kit modifié crée
        sa révision XMFG18 + une ligne d'audit récapitulative."""
        from ..services import remplacer_composant_masse
        donnees = corps_objet(request)
        # CI #997 fuzz (4) — corps typé comme le schéma publié : identifiants
        # entiers non nuls, `dry_run` booléen JSON (`0` lisait « appliquer »,
        # et appliquait réellement le remplacement), ratio décimal > 0.
        types_corps_ou_400(donnees, ids=('produit_ancien', 'produit_nouveau'), nuls=())
        dry_run = donnees.get('dry_run', True)
        if not isinstance(dry_run, bool):
            raise ValidationError({'dry_run': ['Booléen attendu (true/false).']})
        ratio = donnees.get('ratio_quantite')
        if ratio is not None:
            try:
                ratio = RATIO_REMPLACEMENT.run_validation(ratio)
            except ValidationError as exc:
                raise ValidationError({'ratio_quantite': exc.detail})
            if ratio < RATIO_REMPLACEMENT.min_value:  # la borne est publiée, le contrôle est ici
                raise ValidationError({'ratio_quantite': ['Le ratio de quantité doit être positif.']})
        # CI #997 fuzz (3/4) — ``0`` ne désigne aucun produit (400) ; deux fois le
        # même produit : l'état demandé s'oppose à lui-même, le corps était conforme (409).
        ancien, nouveau = (id_corps(donnees.get(c)) for c in ('produit_ancien', 'produit_nouveau'))
        if ancien is None or nouveau is None:
            return Response({'detail': 'Produit introuvable pour cette société.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if ancien == nouveau:
            return Response({'detail': 'Le produit de remplacement doit être différent du produit remplacé.'},
                            status=status.HTTP_409_CONFLICT)
        try:
            resultat = remplacer_composant_masse(
                request.user.company,
                produit_ancien_id=ancien,
                produit_nouveau_id=nouveau,
                ratio_quantite=ratio,
                dry_run=dry_run,
                user=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat)
