from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from drf_spectacular.utils import extend_schema
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
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
        try:
            transfert = transfer_stock(
                company=request.user.company, user=request.user,
                produit_id=request.data.get('produit'),
                source_id=request.data.get('source'),
                destination_id=request.data.get('destination'),
                quantite=request.data.get('quantite'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(transfert).data,
                        status=status.HTTP_201_CREATED)

    # ── NTRET7 — cycle en deux temps (OPT-IN, le direct reste inchangé) ────

    @extend_schema(request=None, responses={201: TransfertStockSerializer})
    @action(detail=False, methods=['post'], url_path='demander')
    def demander(self, request):
        """NTRET7 — ouvre un transfert EN DEUX TEMPS : rien n'a encore bougé.

        Le transfert DIRECT (``POST transferts/``) reste strictement
        inchangé — ce cycle est une porte d'entrée SÉPARÉE."""
        from ..services_transfert_deux_temps import creer_demande_transfert

        try:
            transfert = creer_demande_transfert(
                company=request.user.company, user=request.user,
                produit_id=request.data.get('produit'),
                source_id=request.data.get('source'),
                destination_id=request.data.get('destination'),
                quantite=request.data.get('quantite'),
                note=request.data.get('note') or '')
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
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
                            status=status.HTTP_400_BAD_REQUEST)
        transfert.refresh_from_db()
        return Response(self.get_serializer(transfert).data)

    @extend_schema(request=None, responses={200: TransfertStockSerializer})
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
                            status=status.HTTP_400_BAD_REQUEST)
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
