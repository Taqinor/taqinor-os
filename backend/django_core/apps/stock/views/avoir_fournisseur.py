from django.db import transaction  # noqa: F401
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.parsers import JSONParser
from rest_framework import viewsets, filters, status  # noqa: F401
from rest_framework.decorators import action  # noqa: F401
from rest_framework.response import Response  # noqa: F401
from rest_framework import serializers
from ..openapi_helpers import INT, P, corps
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


@extend_schema_view(list=extend_schema(parameters=[P('fournisseur', INT)]))
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

    parser_classes = [JSONParser]

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            # ASTK246 — montants réglés : règle UNIQUE des règlements fournisseur.
            from .paiement_fournisseur import PeutLirePaiementsFournisseur
            return [PeutLirePaiementsFournisseur()]
        elif self.action in WRITE_ACTIONS + ['valider', 'imputer']:
            # ASTK19 (D-ASTK-3) — créer/valider/imputer un avoir = « payer ».
            return [HasPermissionOrLegacy('achats_payer')()]
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

    def update(self, request, *args, **kwargs):
        """ASTK24 — seul un avoir BROUILLON se modifie : validé ou imputé,
        ses montants et son fournisseur sont figés (les imputations portent
        déjà sur ces montants)."""
        avoir = self.get_object()
        if avoir.statut != AvoirFournisseur.Statut.BROUILLON:
            return Response(
                {'detail': 'Avoir validé : non modifiable.'},
                status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        """ASTK85 — un avoir portant au moins une imputation sur une
        facture n'est jamais supprimable (la CASCADE effaçait l'imputation et
        relevait le solde dû de la facture en silence). Même patron que la
        garde paiements de ``FactureFournisseurViewSet.perform_destroy``."""
        from rest_framework.exceptions import ValidationError
        imputations = list(
            instance.imputations.select_related('facture'))
        if imputations:
            refs = ', '.join(sorted({
                i.facture.reference for i in imputations}))
            raise ValidationError({
                'detail': (
                    f'Cet avoir fournisseur est imputé sur {refs} '
                    f'(montant imputé : {instance.montant_impute} MAD) : '
                    'suppression refusée.'
                ),
            })
        instance.delete()

    @extend_schema(request=None, responses=AvoirFournisseurSerializer)
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

    @extend_schema(request=corps('AvoirImputerCorps', facture=serializers.IntegerField(), montant=serializers.DecimalField(max_digits=14, decimal_places=2, required=False)), responses=AvoirFournisseurSerializer)
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
