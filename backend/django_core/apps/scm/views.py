"""Vues de planification supply chain (Groupe NTSCM).

Accès réservé Responsable/Administrateur (données de planification achat —
même palier que les modules de conformité/planification voisins, ex.
``apps.fiscal``) : ``get_permissions`` renvoie ``[IsResponsableOrAdmin()]``
sur chaque viewset, société toujours scopée par ``CompanyScopedModelViewSet``.
"""
from authentication.permissions import IsResponsableOrAdmin
from core.viewsets import CompanyScopedModelViewSet

from .models import PrevisionDemande
from .serializers import PrevisionDemandeSerializer


class PrevisionDemandeViewSet(CompanyScopedModelViewSet):
    """CRUD des prévisions de demande (NTSCM1) + génération automatique
    (NTSCM2/3, voir la ``@action`` ``generer`` posée par ce lot)."""
    queryset = PrevisionDemande.objects.select_related(
        'produit', 'genere_par').all()
    serializer_class = PrevisionDemandeSerializer
    filterset_fields = ['produit', 'segment']

    def get_permissions(self):
        return [IsResponsableOrAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        periode_min = self.request.query_params.get('periode_min')
        periode_max = self.request.query_params.get('periode_max')
        if periode_min:
            qs = qs.filter(periode__gte=periode_min)
        if periode_max:
            qs = qs.filter(periode__lte=periode_max)
        return qs
