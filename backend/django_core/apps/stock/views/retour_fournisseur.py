from django.db import transaction  # noqa: F401
from django.db.models import ProtectedError, Count, Min, Max  # noqa: F401
from django.http import HttpResponse  # noqa: F401
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
    AvoirFournisseurSerializer,
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


class RetourFournisseurViewSet(CompanyScopedModelViewSet):
    """N19 — retours fournisseur (articles défectueux / erronés). Numérotation
    sans trou (préfixe RF). La validation DÉCRÉMENTE le stock via MouvementStock
    (SORTIE). Usage INTERNE."""
    queryset = RetourFournisseur.objects.select_related(
        'fournisseur', 'bon_commande', 'created_by',
    ).prefetch_related('lignes__produit').all()
    serializer_class = RetourFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'fournisseur__nom', 'motif']
    ordering_fields = ['date_creation', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + [
            'valider', 'annuler', 'generer_avoir',
        ]:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(RetourFournisseur, 'RF', company, _save)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide le retour : décrémente le stock (SORTIE) pour chaque ligne.
        Idempotent : un retour déjà validé/annulé ne re-décrémente jamais."""
        from ..services import apply_retour_fournisseur
        retour = self.get_object()
        try:
            apply_retour_fournisseur(retour, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(retour).data)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        retour = self.get_object()
        if retour.statut == RetourFournisseur.Statut.VALIDE:
            return Response(
                {'detail': 'Un retour validé ne peut pas être annulé '
                           '(le stock a déjà été décrémenté).'},
                status=status.HTTP_400_BAD_REQUEST)
        retour.statut = RetourFournisseur.Statut.ANNULE
        retour.save(update_fields=['statut'])
        return Response(self.get_serializer(retour).data)

    @action(detail=True, methods=['post'], url_path='generer-avoir')
    def generer_avoir(self, request, pk=None):
        """XPUR9 — génère un AvoirFournisseur BROUILLON pré-rempli depuis ce
        retour VALIDÉ (« attente d'avoir » tant que non reçu). Refuse si le
        retour n'est pas validé ou a déjà un avoir."""
        from ..services import creer_avoir_depuis_retour
        retour = self.get_object()
        try:
            avoir = creer_avoir_depuis_retour(
                request.user.company, retour, user=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            AvoirFournisseurSerializer(avoir).data,
            status=status.HTTP_201_CREATED)
