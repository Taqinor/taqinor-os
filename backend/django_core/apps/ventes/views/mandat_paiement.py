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
from rest_framework.decorators import action
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet  # ARC5
from ..models import MandatPaiement
from ..serializers import MandatPaiementSerializer

READ_ACTIONS = ['list', 'retrieve']


class MandatPaiementViewSet(CompanyScopedModelViewSet):
    # ARC5 — sweep TenantMixin : base transverse unique. get_queryset et
    # perform_create SURCHARGENT la base (scoping direct sur `company` + filtre
    # ?client). Le `permission_classes = [IsResponsableOrAdmin]` posé ici prime
    # sur le défaut ScopedPermission de la base (attribut de classe DRF) : la
    # matrice 401/403/404 est INCHANGÉE (règle #4 : rien touché côté statut).
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
