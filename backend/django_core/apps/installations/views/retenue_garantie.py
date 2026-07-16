"""Vue FG309 — retenue de garantie sur sous-traitant (pratique BTP marocaine).

``RetenueGarantieSousTraitantViewSet`` : CRUD des retenues de garantie (%) sur un
ordre de sous-traitance (FG305), plus l'action ``lever`` qui libère la retenue à
la levée des réserves. Lecture & écriture responsable/admin (montants INTERNES).
Multi-tenant via ``TenantMixin`` : société + ``created_by`` posés côté serveur ;
l'``ordre`` ciblé est validé tenant.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import RetenueGarantieSousTraitant
from ..serializers import RetenueGarantieSousTraitantSerializer


class RetenueGarantieSousTraitantViewSet(CompanyScopedModelViewSet):
    """FG309 — retenues de garantie sous-traitant. Lecture & écriture
    responsable/admin (montants INTERNES). Société + `created_by` posés serveur ;
    `ordre` validé tenant. Filtrable par `ordre` et `levee`. Libération via
    l'action `lever`."""
    queryset = RetenueGarantieSousTraitant.objects.select_related(
        'ordre', 'created_by').all()
    serializer_class = RetenueGarantieSousTraitantSerializer
    permission_classes = [IsResponsableOrAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        ordre = params.get('ordre')
        if ordre:
            qs = qs.filter(ordre_id=ordre)
        levee = params.get('levee')
        if levee is not None and levee != '':
            qs = qs.filter(levee=levee.lower() in ('1', 'true', 'vrai', 'oui'))
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        ordre = serializer.validated_data.get('ordre')
        if ordre is not None and getattr(ordre, 'company_id', None) != getattr(
                company, 'id', None):
            raise ValidationError(
                {'ordre': 'Ordre inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def lever(self, request, pk=None):
        """FG309 — lève la retenue (réserves levées) : pose `levee=True` et la
        date de levée. Idempotent. Réservé responsable/admin."""
        retenue = self.get_object()
        if not retenue.levee:
            retenue.levee = True
            retenue.date_levee = timezone.now().date()
            retenue.save(update_fields=['levee', 'date_levee',
                                        'date_modification'])
        return Response(self.get_serializer(retenue).data,
                        status=status.HTTP_200_OK)
