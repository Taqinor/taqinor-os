"""XCTR22 — Mandat de paiement récurrent (tokenisation carte) — gestion
interne (responsable/admin). La tokenisation elle-même (le client enregistre
sa carte) est un flux portail séparé (XCTR14) ; ce viewset couvre la vue
interne + la révocation + le débit manuel de test.

Endpoints :
  GET    /ventes/mandats-paiement/               list (par société)
  GET    /ventes/mandats-paiement/{id}/          retrieve
  POST   /ventes/mandats-paiement/{id}/revoquer/ révoque le mandat
"""
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from ..models import MandatPaiement
from ..serializers import MandatPaiementSerializer

READ_ACTIONS = ['list', 'retrieve']


class MandatPaiementViewSet(viewsets.ModelViewSet):
    queryset = MandatPaiement.objects.select_related('client').all()
    serializer_class = MandatPaiementSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, 'company_id', None):
            qs = qs.filter(company=user.company)
        elif not user.is_superuser:
            return qs.none()
        client_id = self.request.query_params.get('client')
        if client_id:
            qs = qs.filter(client_id=client_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'], url_path='revoquer')
    def revoquer(self, request, pk=None):
        """Révocation immédiate — retour au chemin d'encaissement manuel."""
        mandat = self.get_object()
        mandat.statut = MandatPaiement.Statut.REVOQUE
        mandat.revoked_at = timezone.now()
        mandat.save(update_fields=['statut', 'revoked_at'])
        return Response(MandatPaiementSerializer(mandat).data)
