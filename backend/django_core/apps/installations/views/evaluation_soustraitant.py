"""Vue FG308 — évaluations de performance des sous-traitants chantier.

``EvaluationSousTraitantViewSet`` : CRUD des notes de performance (qualité /
délai / sécurité, 1–5) d'un sous-traitant, plus une action ``scorecard`` qui
renvoie la moyenne cumulée par axe. Lecture tout rôle, écriture responsable/admin.
Multi-tenant via ``TenantMixin`` : société + ``evalue_par`` posés côté serveur ;
``sous_traitant`` / ``ordre`` / ``chantier`` validés tenant.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.mixins import TenantMixin
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin

from ..models import EvaluationSousTraitant, SousTraitant
from ..serializers import EvaluationSousTraitantSerializer
from .. import selectors

READ_ACTIONS = ['list', 'retrieve', 'scorecard']


def _check_tenant(serializer, company, field):
    cid = getattr(company, 'id', None)
    obj = serializer.validated_data.get(field)
    if obj is not None and getattr(obj, 'company_id', None) != cid:
        raise ValidationError({field: 'Objet inconnu pour cette société.'})


class EvaluationSousTraitantViewSet(TenantMixin, viewsets.ModelViewSet):
    """FG308 — évaluations de performance sous-traitant. Lecture tout rôle,
    écriture responsable/admin. Société + `evalue_par` posés serveur ; FK liées
    validées tenant. Filtrable par `sous_traitant`, `ordre`, `chantier`."""
    queryset = EvaluationSousTraitant.objects.select_related(
        'sous_traitant', 'ordre', 'chantier', 'evalue_par').all()
    serializer_class = EvaluationSousTraitantSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for key, col in (('sous_traitant', 'sous_traitant_id'),
                         ('ordre', 'ordre_id'),
                         ('chantier', 'chantier_id')):
            val = params.get(key)
            if val:
                qs = qs.filter(**{col: val})
        return qs

    def perform_create(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'sous_traitant')
        _check_tenant(serializer, company, 'ordre')
        _check_tenant(serializer, company, 'chantier')
        serializer.save(company=company, evalue_par=self.request.user)

    def perform_update(self, serializer):
        company = self.request.user.company
        _check_tenant(serializer, company, 'sous_traitant')
        _check_tenant(serializer, company, 'ordre')
        _check_tenant(serializer, company, 'chantier')
        serializer.save(company=company)

    @action(detail=False, methods=['get'])
    def scorecard(self, request):
        """FG308 — scorecard cumulée d'un sous-traitant (moyenne par axe + note
        globale). Param `sous_traitant` requis. Lecture seule."""
        st_id = request.query_params.get('sous_traitant')
        if not st_id:
            return Response(
                {'detail': 'Paramètre `sous_traitant` requis.'},
                status=status.HTTP_400_BAD_REQUEST)
        st = SousTraitant.objects.filter(
            id=st_id, company=request.user.company).first()
        if st is None:
            return Response(
                {'detail': 'Sous-traitant inconnu pour cette société.'},
                status=status.HTTP_404_NOT_FOUND)
        data = selectors.sous_traitant_scorecard(st)
        data['sous_traitant'] = st.id
        return Response(data)
