"""Vues FG321 — bons de prélèvement (pick list) par chantier.

``PickListViewSet`` : à la création, génère le bon depuis les réservations
actives du chantier (``services.generer_picklist_pour_chantier``), une ligne par
SKU ordonnée par casier. Cycle de progression ``demarrer`` / ``terminer``.
``PickListLigneViewSet`` : coche les lignes (`preleve` / `quantite_prelevee`).
Lecture tout rôle, écriture responsable/admin. Multi-tenant via ``TenantMixin`` ;
le chantier référencé est validé tenant.
"""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from apps.ventes.utils.references import create_with_reference

from ..models import PickList, PickListLigne
from ..serializers import PickListSerializer, PickListLigneSerializer
from .. import services

READ_ACTIONS = ['list', 'retrieve']


class PickListViewSet(CompanyScopedModelViewSet):
    """FG321 — bons de prélèvement. Lecture tout rôle, écriture
    responsable/admin. Référence/société/`created_by` posés serveur ; les
    lignes sont générées serveur depuis les réservations. Filtrable par
    `installation`, `statut`."""
    queryset = PickList.objects.select_related(
        'installation', 'created_by').prefetch_related('lignes').all()
    serializer_class = PickListSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        installation = params.get('installation')
        if installation:
            qs = qs.filter(installation_id=installation)
        statut = params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def _check_tenant(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        installation = serializer.validated_data.get('installation')
        if installation is not None and getattr(
                installation, 'company_id', None) != cid:
            raise ValidationError(
                {'installation': 'Chantier inconnu pour cette société.'})

    def perform_create(self, serializer):
        company = self.request.user.company
        self._check_tenant(serializer)
        installation = serializer.validated_data.get('installation')
        note = serializer.validated_data.get('note')

        def _save(reference):
            pick = services.generer_picklist_pour_chantier(
                installation, company, created_by=self.request.user,
                reference=reference)
            if note:
                pick.note = note
                pick.save(update_fields=['note', 'date_modification'])
            return pick

        pick = create_with_reference(PickList, 'PICK', company, _save)
        serializer.instance = pick

    def perform_update(self, serializer):
        self._check_tenant(serializer)
        serializer.save(company=self.request.user.company)

    @action(detail=True, methods=['post'])
    def demarrer(self, request, pk=None):
        """FG321 — passe le bon en cours."""
        pick = self.get_object()
        pick.statut = PickList.Statut.EN_COURS
        pick.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(pick).data)

    @action(detail=True, methods=['post'])
    def terminer(self, request, pk=None):
        """FG321 — clôture le bon (→ terminé)."""
        pick = self.get_object()
        pick.statut = PickList.Statut.TERMINE
        pick.save(update_fields=['statut', 'date_modification'])
        return Response(self.get_serializer(pick).data)


class PickListLigneViewSet(viewsets.ModelViewSet):
    """FG321 — lignes de prélèvement. Pas de `company` propre : scope via le bon
    parent. Filtrable par `pick_list`. Lecture tout rôle, écriture
    responsable/admin (typiquement pour cocher `preleve`)."""
    queryset = PickListLigne.objects.select_related(
        'pick_list', 'produit', 'bin').all()
    serializer_class = PickListLigneSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.company_id:
            qs = qs.filter(pick_list__company=user.company)
        elif not user.is_superuser:
            qs = qs.none()
        pick_list = self.request.query_params.get('pick_list')
        if pick_list:
            qs = qs.filter(pick_list_id=pick_list)
        return qs

    def _check_parent(self, serializer):
        company = self.request.user.company
        cid = getattr(company, 'id', None)
        pick = serializer.validated_data.get('pick_list')
        if pick is not None and getattr(pick, 'company_id', None) != cid:
            raise ValidationError(
                {'pick_list': 'Bon inconnu pour cette société.'})

    def perform_create(self, serializer):
        self._check_parent(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._check_parent(serializer)
        serializer.save()
