"""Vues FG327 — stock en consignation / emballages consignés.

``MaterielConsigneViewSet`` : CRUD du matériel consigné retournable ; société/
`created_by` posés serveur ; action ``retourner`` (→ retourné, pose
`retourne_par`/`date_retour`). Lecture tout rôle, écriture responsable/admin.
Multi-tenant via ``TenantMixin`` ; fournisseur validé tenant. Cross-app :
``stock.Fournisseur`` en string-FK.
"""
from django.utils import timezone

from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import MaterielConsigne
from ..serializers import MaterielConsigneSerializer

READ_ACTIONS = ['list', 'retrieve']


class MaterielConsigneViewSet(CompanyScopedModelViewSet):
    """FG327 — matériel consigné. Lecture tout rôle, écriture responsable/admin.
    Filtrable par `statut`, `type_materiel`, `fournisseur`."""
    queryset = MaterielConsigne.objects.select_related(
        'fournisseur', 'retourne_par', 'created_by').all()
    serializer_class = MaterielConsigneSerializer

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
        type_materiel = params.get('type_materiel')
        if type_materiel:
            qs = qs.filter(type_materiel=type_materiel)
        fournisseur = params.get('fournisseur')
        if fournisseur:
            qs = qs.filter(fournisseur_id=fournisseur)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        fournisseur = serializer.validated_data.get('fournisseur')
        if fournisseur is not None and getattr(
                fournisseur, 'company_id', None) != cid:
            raise ValidationError(
                {'fournisseur': 'Fournisseur inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_tenant(serializer)
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def retourner(self, request, pk=None):
        """FG327 — solde le lot consigné (→ retourné, pose
        `retourne_par`/`date_retour`)."""
        mc = self.get_object()
        mc.statut = MaterielConsigne.Statut.RETOURNE
        mc.retourne_par = request.user
        mc.date_retour = timezone.now().date()
        mc.save(update_fields=[
            'statut', 'retourne_par', 'date_retour', 'date_modification'])
        return Response(self.get_serializer(mc).data)
