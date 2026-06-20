from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from authentication.mixins import TenantMixin  # noqa: F401
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


class ReceptionFournisseurViewSet(TenantMixin, viewsets.ModelViewSet):
    """G5 — Réceptions fournisseur (goods-in / entrée de marchandises).

    Numérotation sans trou (préfixe REC). La confirmation incrémente le stock
    via MouvementStock (ENTREE) pour chaque ligne reçue, avance les quantités
    reçues du BCF et son statut, et reste IDEMPOTENTE (une réception confirmée
    ne re-crée jamais de mouvement). Usage INTERNE."""
    queryset = ReceptionFournisseur.objects.select_related(
        'bon_commande', 'bon_commande__fournisseur', 'recu_par', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = ReceptionFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'reference', 'bon_commande__reference',
        'bon_commande__fournisseur__nom', 'note',
    ]
    ordering_fields = ['date_creation', 'date_reception', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['confirmer', 'annuler']:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        bon_id = self.request.query_params.get('bon_commande')
        if bon_id:
            qs = qs.filter(bon_commande_id=bon_id)
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(ReceptionFournisseur, 'REC', company, _save)

    @action(detail=True, methods=['post'], url_path='confirmer')
    def confirmer(self, request, pk=None):
        """Confirme la réception : incrémente le stock (ENTREE) pour chaque
        ligne reçue et avance le statut du BCF. Idempotent : une réception déjà
        confirmée ne re-crée jamais de mouvement."""
        from ..services import confirm_reception_fournisseur
        reception = self.get_object()
        try:
            confirm_reception_fournisseur(reception, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(reception).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        reception = self.get_object()
        if reception.statut == ReceptionFournisseur.Statut.CONFIRME:
            return Response(
                {'detail': 'Une réception confirmée ne peut pas être annulée '
                           '(le stock a déjà été incrémenté).'},
                status=status.HTTP_400_BAD_REQUEST)
        reception.statut = ReceptionFournisseur.Statut.ANNULE
        reception.save(update_fields=['statut'])
        return Response(self.get_serializer(reception).data)
