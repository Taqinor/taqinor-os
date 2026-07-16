"""Vues du registre des assurances & sinistres d'entreprise (NTASS)."""
from django.db import IntegrityError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from core.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin

from .models import Assureur, Courtier, PoliceAssurance
from .serializers import (
    AssureurSerializer, CourtierSerializer, PoliceAssuranceSerializer,
)


class _AssurancesBaseViewSet(
        WriteScopedPermissionMixin, TenantMixin, viewsets.ModelViewSet):
    """Base commune : société scopée (TenantMixin) + lecture/écriture
    fine-grainées (NTASS29 — ``assurances_voir``/``assurances_gerer``).

    Comptes légacy sans rôle fin : repli historique Responsable/Administrateur
    préservé (voir ``core.permissions.WriteScopedPermissionMixin``)."""
    read_permission = 'assurances_voir'
    write_permission = 'assurances_gerer'


class AssureurViewSet(_AssurancesBaseViewSet):
    """CRUD des assureurs (compagnies d'assurance), scopé société (NTASS1)."""
    queryset = Assureur.objects.all()
    serializer_class = AssureurSerializer
    filterset_fields = ['actif']


class CourtierViewSet(_AssurancesBaseViewSet):
    """CRUD des courtiers/intermédiaires d'assurance, scopé société (NTASS1)."""
    queryset = Courtier.objects.all()
    serializer_class = CourtierSerializer
    filterset_fields = ['actif']


class PoliceAssuranceViewSet(_AssurancesBaseViewSet):
    """CRUD des polices d'assurance d'entreprise, scopé société (NTASS2)."""
    queryset = PoliceAssurance.objects.select_related('assureur', 'courtier')
    serializer_class = PoliceAssuranceSerializer
    filterset_fields = ['type_police', 'statut', 'assureur', 'courtier']

    def perform_create(self, serializer):
        try:
            super().perform_create(serializer)
        except IntegrityError:
            # Filet de course sur (company, numero_police) — la contrainte DB
            # se déclenche entre la validation serializer et l'écriture.
            raise ValidationError(
                {'numero_police':
                 'Ce numéro de police existe déjà dans votre société.'})

    def perform_update(self, serializer):
        try:
            super().perform_update(serializer)
        except IntegrityError:
            raise ValidationError(
                {'numero_police':
                 'Ce numéro de police existe déjà dans votre société.'})
