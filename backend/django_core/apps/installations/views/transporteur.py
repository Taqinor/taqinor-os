"""Vues FG331 — transporteurs & tarifs de transport.

``TransporteurViewSet`` : CRUD des transporteurs ; société/`created_by` posés
serveur. Le coût de course se porte sur la livraison (FG329, champ
`cout_transport`). Lecture tout rôle, écriture responsable/admin. Multi-tenant
via ``TenantMixin``.
"""
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from ..models import Transporteur
from ..serializers import TransporteurSerializer

READ_ACTIONS = ['list', 'retrieve']


class TransporteurViewSet(CompanyScopedModelViewSet):
    """FG331 — transporteurs. Lecture tout rôle, écriture responsable/admin.
    Filtrable par `type_transporteur`, `active`.

    ARC2 — pilote : base transverse unique (TenantMixin + ModelViewSet). Le
    get_queryset (filtres de requête) et perform_create/perform_update (company
    + created_by forcés serveur) SURCHARGENT la base : réponses inchangées."""
    queryset = Transporteur.objects.select_related('created_by').all()
    serializer_class = TransporteurSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        type_transporteur = params.get('type_transporteur')
        if type_transporteur:
            qs = qs.filter(type_transporteur=type_transporteur)
        active = params.get('active')
        if active in ('0', 'false', 'False'):
            qs = qs.filter(active=False)
        elif active in ('1', 'true', 'True'):
            qs = qs.filter(active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company,
            created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(company=self.request.user.company)
