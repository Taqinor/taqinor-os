"""Vues (ViewSets) de l'app `apps.transport` — toutes scopées société via
`core.viewsets.CompanyScopedModelViewSet` (jamais un `ModelViewSet` nu,
SCA4)."""
from rest_framework.exceptions import ValidationError

from core.viewsets import CompanyScopedModelViewSet

from . import services
from .models import OrdreTransport
from .serializers import OrdreTransportSerializer


def _check_same_company(request, **fields):
    """Refuse (400) toute FK référençant un objet d'une AUTRE société — une
    `PrimaryKeyRelatedField` DRF n'est, par défaut, PAS scopée société ; sans
    ce garde un id valide d'une autre société serait accepté (IDOR)."""
    company = request.user.company
    cid = getattr(company, 'id', None)
    for name, obj in fields.items():
        if obj is not None and getattr(obj, 'company_id', None) != cid:
            raise ValidationError({name: 'Référence inconnue pour cette société.'})


class OrdreTransportViewSet(CompanyScopedModelViewSet):
    """NTLOG1 — ordre de transport. Filtrable par `?statut=`. `numero` posé
    côté serveur à la création (`services.attribuer_numero`, anti-collision,
    ARC6)."""

    queryset = OrdreTransport.objects.select_related('created_by').all()
    serializer_class = OrdreTransportSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        statut = self.request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)
        return qs

    def perform_create(self, serializer):
        serializer.save(
            company=self.request.user.company, created_by=self.request.user)
        services.attribuer_numero(serializer.instance)
