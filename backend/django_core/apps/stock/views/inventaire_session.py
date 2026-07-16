"""FG63 — Session d'inventaire physique (draft / valider).

Remplace l'action `inventaire` one-shot par un workflow draft/valider :
- POST /inventaire-sessions/ → créer une session en brouillon
- GET/PATCH/PUT /inventaire-sessions/{id}/ → lire/modifier la session
- POST /inventaire-sessions/{id}/valider/ → émettre les ajustements
- POST /inventaire-sessions/{id}/annuler/ → annuler (si brouillon)

INTERNE — admin uniquement ; les écarts de stock ne sont jamais exposés
au client.
"""
from django.db import transaction  # noqa: F401
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.viewsets import CompanyScopedModelViewSet
from apps.ventes.utils.references import create_with_reference
from ..models import InventaireSession
from ..serializers import InventaireSessionSerializer
from authentication.permissions import IsAdminRole

READ_ACTIONS = ['list', 'retrieve']


class InventaireSessionViewSet(CompanyScopedModelViewSet):
    """FG63 — Sessions de comptage physique du stock (draft → valider)."""
    queryset = InventaireSession.objects.prefetch_related(
        'lignes__produit').all()
    serializer_class = InventaireSessionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'motif']
    ordering_fields = ['date_creation', 'statut', 'reference']
    ordering = ['-date_creation']

    def get_permissions(self):
        return [IsAdminRole()]

    def perform_create(self, serializer):
        company = self.request.user.company

        def _save(ref):
            return serializer.save(
                reference=ref,
                company=company,
                created_by=self.request.user,
            )
        create_with_reference(InventaireSession, 'INV', company, _save)

    @action(detail=True, methods=['post'], url_path='valider')
    def valider(self, request, pk=None):
        """Valide la session : émet les AJUSTEMENT de stock pour chaque écart."""
        from ..services import valider_inventaire_session
        session = self.get_object()
        try:
            result = valider_inventaire_session(session, request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """Annule une session en brouillon."""
        session = self.get_object()
        if session.statut != InventaireSession.Statut.BROUILLON:
            return Response(
                {'detail': 'Seule une session en brouillon peut être annulée.'},
                status=status.HTTP_400_BAD_REQUEST)
        session.statut = InventaireSession.Statut.ANNULE
        session.save(update_fields=['statut'])
        return Response(self.get_serializer(session).data)
