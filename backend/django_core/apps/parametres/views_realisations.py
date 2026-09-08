"""ViewSet du catalogue « Réalisations » (ordre fondateur 08/09/2026).

Même schéma de permission que les autres réglages de Paramètres
(``views_referentiels._ReferentielViewSet``) :

  * lecture (``list``/``retrieve``) : tout rôle (``IsAnyRole``) — le moteur de
    relances doit pouvoir lire le catalogue ;
  * écriture : Administrateur ou Responsable promu
    (``IsAdminOrResponsableTier``), jamais le palier limité.

``company`` est filtrée ET forcée côté serveur par
``CompanyScopedModelViewSet`` (socle ARC2) — jamais lue du corps.
"""
from authentication.permissions import IsAdminOrResponsableTier, IsAnyRole
from core.viewsets import CompanyScopedModelViewSet

from .models_realisations import Realisation
from .serializers_realisations import RealisationSerializer

READ_ACTIONS = ['list', 'retrieve']


class RealisationViewSet(CompanyScopedModelViewSet):
    """Catalogue des installations réelles de la société. ``?actif=true``."""

    queryset = Realisation.objects.all()
    serializer_class = RealisationSerializer

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        return [IsAdminOrResponsableTier()]

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('true', '1'):
            qs = qs.filter(actif=True)
        return qs
