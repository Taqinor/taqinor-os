from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.parsers import JSONParser
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import serializers
from core.champs_stricts import ChaineStricte
from ..erreurs_achats import EtatIncompatible, statut_refus_metier
from ..openapi_helpers import P, STR, corps
from ..utils.params import ID_MAX, corps_objet, types_corps_ou_400
from core.viewsets import CompanyScopedModelViewSet
from ..models import TransfertStock
from ..serializers import TransfertStockSerializer
from authentication.permissions import IsAnyRole, IsAdminRole, HasPermissionOrLegacy

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.

_ID = {'min_value': 1, 'max_value': ID_MAX}
MSG_SOURCE_EGALE_DESTINATION = 'La source et la destination doivent être différentes.'


def _corps_transfert(request):
    """CI #997 fuzz (4) — corps d'un transfert lu comme le schéma le publie :
    produit / source / destination (identifiants entiers) et quantité (entier)
    REQUIS, note texte facultative (``null`` permis). La même source et
    destination est un état refusé (409) : deux identifiants conformes dont
    l'égalité s'oppose, ce que le schéma ne sait pas dire."""
    donnees = corps_objet(request)
    types_corps_ou_400(donnees, textes=('note',), entiers=('quantite',),
                       ids=('produit', 'source', 'destination'), nuls=('note',))
    manquants = {c: ['Ce champ est obligatoire.']
                 for c in ('produit', 'source', 'destination', 'quantite') if donnees.get(c) is None}
    if manquants:
        raise ValidationError(manquants)
    if '\x00' in (donnees.get('note') or ''):
        raise ValidationError({'note': ['Le caractère nul n’est pas autorisé.']})
    return donnees


def _meme_emplacement(donnees):
    """409 si la source égale la destination, ``None`` sinon."""
    if donnees['source'] != donnees['destination']:
        return None
    return Response({'detail': MSG_SOURCE_EGALE_DESTINATION}, status=status.HTTP_409_CONFLICT)


@extend_schema_view(list=extend_schema(parameters=[P('statut', STR)]))
class TransfertStockViewSet(CompanyScopedModelViewSet):
    """N15 — transferts de stock entre emplacements (le « transfer record »).

    Lecture seule + création. La création passe par le service `transfer_stock`
    (validation + atomicité), jamais par un save direct. Le total
    `Produit.quantite_stock` n'est jamais modifié par un transfert."""
    queryset = TransfertStock.objects.select_related(
        'produit', 'source', 'destination', 'created_by').all()
    serializer_class = TransfertStockSerializer
    http_method_names = ['get', 'post', 'head', 'options']
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['produit__nom', 'note']
    ordering_fields = ['date', 'quantite']
    ordering = ['-date']

    parser_classes = [JSONParser]

    def get_permissions(self):
        # `get_permissions` prime sur le `permission_classes` d'une @action :
        # chaque action NTRET7 est listée explicitement ici.
        if self.action in READ_ACTIONS + ['bon_pdf']:
            return [IsAnyRole()]
        if self.action in ('create', 'demander', 'expedier', 'receptionner'):
            return [HasPermissionOrLegacy('stock_mouvement')()]
        return [IsAdminRole()]

    def get_queryset(self):
        # Filtrage MANUEL (aucun DjangoFilterBackend branché ici).
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def create(self, request, *args, **kwargs):
        from ..services import transfer_stock
        donnees = _corps_transfert(request)
        refus = _meme_emplacement(donnees)
        if refus is not None:
            return refus
        try:
            transfert = transfer_stock(
                company=request.user.company, user=request.user,
                produit_id=donnees.get('produit'),
                source_id=donnees.get('source'),
                destination_id=donnees.get('destination'),
                quantite=donnees.get('quantite'),
                note=donnees.get('note') or '')
        except EtatIncompatible as exc:  # stock insuffisant, seuil d'approbation : l'état s'oppose (409)
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(transfert).data,
                        status=status.HTTP_201_CREATED)

    # ── NTRET7 — cycle en deux temps (OPT-IN, le direct reste inchangé) ────

    @extend_schema(request=corps('TransfertDemanderCorps', produit=serializers.IntegerField(**_ID),
                                 source=serializers.IntegerField(**_ID), destination=serializers.IntegerField(**_ID),
                                 quantite=serializers.IntegerField(**_ID),
                                 note=ChaineStricte(required=False, allow_blank=True, allow_null=True)),
                   responses={201: TransfertStockSerializer})
    @action(detail=False, methods=['post'], url_path='demander')
    def demander(self, request):
        """NTRET7 — ouvre un transfert EN DEUX TEMPS : rien n'a encore bougé.

        Le transfert DIRECT (``POST transferts/``) reste strictement
        inchangé — ce cycle est une porte d'entrée SÉPARÉE."""
        from ..services_transfert_deux_temps import creer_demande_transfert

        donnees = _corps_transfert(request)
        refus = _meme_emplacement(donnees)
        if refus is not None:
            return refus
        try:
            transfert = creer_demande_transfert(
                company=request.user.company, user=request.user,
                produit_id=donnees.get('produit'),
                source_id=donnees.get('source'),
                destination_id=donnees.get('destination'),
                quantite=donnees.get('quantite'),
                note=donnees.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=statut_refus_metier(exc))
        return Response(self.get_serializer(transfert).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: TransfertStockSerializer})
    @action(detail=True, methods=['post'], url_path='expedier')
    def expedier(self, request, pk=None):
        """Départ du camion : la SOURCE décrémente, la destination attend."""
        from ..services_transfert_deux_temps import expedier_transfert

        transfert = self.get_object()
        try:
            expedier_transfert(transfert, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=statut_refus_metier(exc))
        transfert.refresh_from_db()
        return Response(self.get_serializer(transfert).data)

    @extend_schema(request=corps('TransfertReceptionnerCorps',
                                 quantite_recue=serializers.IntegerField(required=False, min_value=0)),
                   responses={200: TransfertStockSerializer})
    @action(detail=True, methods=['post'], url_path='receptionner')
    def receptionner(self, request, pk=None):
        """Arrivée : la destination n'incrémente QUE le réellement compté
        (``{quantite_recue}``) ; l'écart est journalisé, jamais absorbé."""
        from ..services_transfert_deux_temps import receptionner_transfert

        transfert = self.get_object()
        try:
            receptionner_transfert(
                transfert, request.user,
                quantite_recue=request.data.get('quantite_recue'))
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=statut_refus_metier(exc))
        transfert.refresh_from_db()
        return Response(self.get_serializer(transfert).data)

    @extend_schema(responses={(200, 'application/pdf'): bytes})
    @action(detail=True, methods=['get'], url_path='bon-pdf')
    def bon_pdf(self, request, pk=None):
        """Bon de transfert imprimable (SKU, quantités attendues, code-barres
        du bon à scanner à la réception)."""
        from ..services_transfert_deux_temps import generate_bon_transfert_pdf

        transfert = self.get_object()
        pdf = generate_bon_transfert_pdf(transfert)
        reponse = HttpResponse(pdf, content_type='application/pdf')
        nom = transfert.reference or f'transfert-{transfert.id}'
        reponse['Content-Disposition'] = (
            f'inline; filename="bon-transfert-{nom}.pdf"')
        return reponse
