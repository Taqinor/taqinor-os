"""Vues ZSTK8 — retour / transfert inverse depuis une Livraison validée.

``RetourLivraisonViewSet`` : CRUD des retours + action ``valider`` qui poste
les mouvements ENTREE (plafonnés à la quantité livrée). Généré depuis
``LivraisonViewSet.generer_retour``. Lecture tout rôle, écriture responsable/
admin. Multi-tenant via ``TenantMixin``."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import RetourLivraison, RetourLivraisonLigne
from ..serializers import (
    RetourLivraisonSerializer, RetourLivraisonLigneSerializer,
)
from ..services import valider_retour_livraison

READ_ACTIONS = ['list', 'retrieve']


class RetourLivraisonViewSet(CompanyScopedModelViewSet):
    """ZSTK8 — retours client générés depuis une livraison livrée. Lecture
    tout rôle, écriture responsable/admin. Filtrable par `livraison`,
    `statut`."""
    queryset = RetourLivraison.objects.select_related(
        'livraison', 'created_by').prefetch_related('lignes').all()
    serializer_class = RetourLivraisonSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        livraison = params.get('livraison')
        if livraison:
            qs = qs.filter(livraison_id=livraison)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        livraison = serializer.validated_data.get('livraison')
        if livraison is not None and livraison.company_id != cid:
            raise ValidationError(
                {'livraison': 'Livraison inconnue pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """ZSTK8 — valide le retour : poste les mouvements ENTREE au dépôt
        source (plafonnés à la quantité livrée). Refuse (400) si une ligne
        dépasse la quantité livrée."""
        retour = self.get_object()
        try:
            valider_retour_livraison(retour, request.user)
        except ValueError as exc:
            return Response(
                {'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        retour.refresh_from_db()
        return Response(self.get_serializer(retour).data)


class RetourLivraisonLigneViewSet(viewsets.ModelViewSet):
    """ZSTK8 — lignes d'un retour de livraison. Pas de `company` propre :
    scope via le retour parent. Filtrable par `retour`."""
    queryset = RetourLivraisonLigne.objects.select_related(
        'retour', 'produit').all()
    serializer_class = RetourLivraisonLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(retour__livraison__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        retour = self.request.query_params.get('retour')
        if retour:
            qs = qs.filter(retour_id=retour)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        retour = serializer.validated_data.get('retour')
        if retour is not None and retour.livraison.company_id != cid:
            raise ValidationError(
                {'retour': 'Retour inconnu pour cette société.'})

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
