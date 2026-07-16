"""Vues FG326 — réapprovisionnement multi-dépôts.

``RegleReapproViewSet`` : CRUD des règles min/max + action ``propositions`` qui
calcule (serveur) les transferts à proposer pour les emplacements sous leur min,
via ``selectors.proposer_reapprovisionnement``. Lecture tout rôle, écriture
responsable/admin. Multi-tenant via ``TenantMixin`` ; produit/emplacements
validés tenant. Cross-app : ``stock`` en string-FK (quantités lues via
``stock.selectors``).
"""
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import RegleReappro
from ..serializers import RegleReapproSerializer
from .. import selectors

READ_ACTIONS = ['list', 'retrieve', 'propositions']


class RegleReapproViewSet(CompanyScopedModelViewSet):
    """FG326 — règles de réapprovisionnement. Lecture tout rôle, écriture
    responsable/admin. Filtrable par `produit`, `emplacement_cible`, `active`."""
    queryset = RegleReappro.objects.select_related(
        'produit', 'emplacement_cible', 'emplacement_source',
        'created_by').all()
    serializer_class = RegleReapproSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        produit = params.get('produit')
        if produit:
            qs = qs.filter(produit_id=produit)
        cible = params.get('emplacement_cible')
        if cible:
            qs = qs.filter(emplacement_cible_id=cible)
        active = params.get('active')
        if active in ('0', 'false', 'False'):
            qs = qs.filter(active=False)
        elif active in ('1', 'true', 'True'):
            qs = qs.filter(active=True)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        for field, label in (
                ('produit', 'Produit'),
                ('emplacement_cible', 'Emplacement cible'),
                ('emplacement_source', 'Emplacement source')):
            obj = serializer.validated_data.get(field)
            if obj is not None and getattr(obj, 'company_id', None) != cid:
                raise ValidationError(
                    {field: f'{label} inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=False, methods=['get'])
    def propositions(self, request):
        """FG326 — liste des transferts proposés (emplacements sous leur min).
        Lecture seule, consultative."""
        result = selectors.proposer_reapprovisionnement(request.user.company)
        return Response(result)
