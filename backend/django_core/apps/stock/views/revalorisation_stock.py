from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.viewsets import CompanyScopedModelViewSet
from ..models import RevalorisationStock
from ..serializers import RevalorisationStockSerializer
from authentication.permissions import IsAdminRole

# NOTE: ce module fait partie du découpage de l'ancien views.py monolithe
# (un module par ressource). Comportement et symboles inchangés : le
# package __init__ ré-exporte toutes les vues publiques.


class RevalorisationStockViewSet(CompanyScopedModelViewSet):
    """XSTK14 — revalorisation manuelle du stock (document tracé). INTERNE,
    admin-only, jamais client-facing. Un brouillon peut être supprimé ; une
    revalorisation VALIDÉE est verrouillée (jamais modifiée/supprimée)."""
    queryset = RevalorisationStock.objects.select_related('produit').all()
    serializer_class = RevalorisationStockSerializer
    permission_classes = [IsAdminRole]
    ordering = ['-date_creation']

    def get_queryset(self):
        qs = super().get_queryset()
        produit_id = self.request.query_params.get('produit')
        if produit_id:
            qs = qs.filter(produit_id=produit_id)
        return qs

    def create(self, request, *args, **kwargs):
        from ..models import Produit
        from ..services import creer_revalorisation
        produit = Produit.objects.filter(
            company=request.user.company,
            id=request.data.get('produit')).first()
        if produit is None:
            return Response(
                {'detail': 'Produit introuvable.'},
                status=status.HTTP_404_NOT_FOUND)
        try:
            revalorisation = creer_revalorisation(
                company=request.user.company, produit=produit,
                nouveau_cout=request.data.get('nouveau_cout'),
                motif=request.data.get('motif'), user=request.user)
        except (ValueError, TypeError) as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            self.get_serializer(revalorisation).data,
            status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.statut == RevalorisationStock.Statut.VALIDEE:
            return Response(
                {'detail': 'Cette revalorisation est validée : verrouillée.'},
                status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.statut == RevalorisationStock.Statut.VALIDEE:
            return Response(
                {'detail': 'Cette revalorisation est validée : verrouillée.'},
                status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide la revalorisation : verrouille le document et devient la
        nouvelle couche de départ du coût moyen. Déjà validée -> 400."""
        from ..services import valider_revalorisation
        revalorisation = self.get_object()
        try:
            valider_revalorisation(revalorisation)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(revalorisation).data)
