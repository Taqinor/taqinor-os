"""Vues FG320 — rangement guidé (put-away).

``PutAwayViewSet`` : CRUD des opérations de rangement. À la création, le casier
suggéré est calculé serveur (``selectors.suggerer_bin_putaway``). L'action
``ranger`` confirme le rangement (casier effectif + statut RANGE + horodatage).
Lecture tout rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
produit/emplacement/casier validés tenant. Cross-app : ``stock`` en string-FK.
"""
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import PutAway, BinLocation
from ..serializers import PutAwaySerializer
from .. import selectors

READ_ACTIONS = ['list', 'retrieve']


class PutAwayViewSet(CompanyScopedModelViewSet):
    """FG320 — rangements guidés. Lecture tout rôle, écriture responsable/admin.
    Société/`created_by`/`bin_suggere` posés serveur. Filtrable par `statut`,
    `produit`, `emplacement`."""
    queryset = PutAway.objects.select_related(
        'produit', 'emplacement', 'bin_suggere', 'bin_effectif',
        'range_par', 'created_by').all()
    serializer_class = PutAwaySerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        produit = params.get('produit')
        if produit:
            qs = qs.filter(produit_id=produit)
        emplacement = params.get('emplacement')
        if emplacement:
            qs = qs.filter(emplacement_id=emplacement)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        produit = serializer.validated_data.get('produit')
        if produit is not None and getattr(
                produit, 'company_id', None) != cid:
            raise ValidationError(
                {'produit': 'Produit inconnu pour cette société.'})
        emplacement = serializer.validated_data.get('emplacement')
        if emplacement is not None and getattr(
                emplacement, 'company_id', None) != cid:
            raise ValidationError(
                {'emplacement': 'Emplacement inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)
        produit = serializer.validated_data.get('produit')
        emplacement = serializer.validated_data.get('emplacement')
        quantite = serializer.validated_data.get('quantite') or 0
        suggestion = selectors.suggerer_bin_putaway(
            company, getattr(produit, 'id', None),
            emplacement_id=getattr(emplacement, 'id', None),
            quantite=quantite)
        serializer.save(
            company=company, created_by=self.request.user,
            bin_suggere=suggestion)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def ranger(self, request, pk=None):
        """FG320 — confirme le rangement. Body optionnel `bin` (casier effectif,
        défaut = casier suggéré). Pose `bin_effectif`/`range_par`/date et passe
        le statut à RANGE."""
        pa = self.get_object()
        company = request.user.company
        bin_id = request.data.get('bin')
        bin_loc = None
        if bin_id:
            bin_loc = BinLocation.objects.filter(
                company=company, id=bin_id).first()
            if bin_loc is None:
                return Response(
                    {'bin': 'Casier inconnu pour cette société.'},
                    status=status.HTTP_400_BAD_REQUEST)
        else:
            bin_loc = pa.bin_suggere
        pa.bin_effectif = bin_loc
        pa.statut = PutAway.Statut.RANGE
        pa.range_par = request.user
        pa.date_rangement = timezone.now()
        pa.save(update_fields=[
            'bin_effectif', 'statut', 'range_par', 'date_rangement',
            'date_modification'])
        return Response(self.get_serializer(pa).data)
