from django.db import transaction  # noqa: F401
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference  # noqa: F401
from ..models import AvoirFournisseur, FactureFournisseur
from ..serializers import AvoirFournisseurSerializer
from authentication.permissions import (  # noqa: F401
    IsAnyRole,
    IsAdminRole,
    IsResponsableOrAdmin,
    HasPermissionOrLegacy,
)

READ_ACTIONS = ['list', 'retrieve']
WRITE_ACTIONS = ['create', 'update', 'partial_update']


class AvoirFournisseurViewSet(CompanyScopedModelViewSet):
    """XPUR9 — avoirs fournisseur (notes de crédit AP). Numérotation sans
    trou (préfixe AVF). `valider` passe brouillon → validé ; `imputer`
    réduit le solde dû d'une facture du même fournisseur. INTERNE."""
    queryset = AvoirFournisseur.objects.select_related(
        'fournisseur', 'retour', 'facture_origine', 'created_by',
    ).prefetch_related('imputations').all()
    serializer_class = AvoirFournisseurSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'fournisseur__nom', 'note']
    ordering_fields = ['date_creation', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        elif self.action in WRITE_ACTIONS + ['valider', 'imputer']:
            return [IsResponsableOrAdmin()]
        elif self.action == 'destroy':
            return [IsAdminRole()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        fournisseur_id = self.request.query_params.get('fournisseur')
        if fournisseur_id:
            qs = qs.filter(fournisseur_id=fournisseur_id)
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref, company=company,
                created_by=self.request.user,
            )
        create_with_reference(AvoirFournisseur, 'AVF', company, _save)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        avoir = self.get_object()
        if avoir.statut != AvoirFournisseur.Statut.BROUILLON:
            return Response(
                {'detail': 'Seul un avoir en brouillon peut être validé.'},
                status=status.HTTP_400_BAD_REQUEST)
        avoir.statut = AvoirFournisseur.Statut.VALIDE
        avoir.save(update_fields=['statut'])
        return Response(self.get_serializer(avoir).data)

    @action(detail=True, methods=['post'], url_path='imputer')
    def imputer(self, request, pk=None):
        """Corps : ``{"facture": <id>, "montant"?: <decimal>}``. Sans
        ``montant``, impute le maximum possible (plafonné par le
        disponible de l'avoir ET le solde dû de la facture)."""
        avoir = self.get_object()
        facture_id = request.data.get('facture')
        if not facture_id:
            return Response(
                {'detail': 'facture est requise.'},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            facture = FactureFournisseur.objects.get(
                pk=facture_id, company=request.user.company)
        except FactureFournisseur.DoesNotExist:
            return Response(
                {'detail': 'Facture introuvable dans cette société.'},
                status=status.HTTP_400_BAD_REQUEST)
        from ..services import imputer_avoir_fournisseur
        try:
            with transaction.atomic():
                imputer_avoir_fournisseur(
                    avoir, facture, request.data.get('montant'),
                    user=request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        avoir.refresh_from_db()
        return Response(self.get_serializer(avoir).data)
