"""Vues du registre des assurances & sinistres d'entreprise (NTASS)."""
from rest_framework import viewsets

from core.mixins import TenantMixin
from core.permissions import WriteScopedPermissionMixin

from .models import Assureur, Courtier
from .serializers import AssureurSerializer, CourtierSerializer


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
