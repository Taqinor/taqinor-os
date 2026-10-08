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
from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminOrResponsableTier, IsAnyRole,
)
from core.viewsets import CompanyScopedModelViewSet

from .models_realisations import Realisation
from .serializers_realisations import RealisationSerializer
from .views_common import SettingsAuditedMixin

READ_ACTIONS = ['list', 'retrieve']


class RealisationViewSet(SettingsAuditedMixin, CompanyScopedModelViewSet):
    """Catalogue des installations réelles de la société. ``?actif=true``.

    APAR28 — chaque écriture est journalisée (``SettingsAuditedMixin``)."""

    queryset = Realisation.objects.all()
    serializer_class = RealisationSerializer
    audit_section = 'realisations'
    audit_libelle = 'Réalisation'

    def get_permissions(self):
        if self.action in READ_ACTIONS:
            return [IsAnyRole()]
        # APAR5 — écriture des réglages société : palier ET droit
        # `parametres_modifier` (même couple qu'ASEC31) — Admin RH,
        # Technicien/Commercial responsable n'y écrivent plus.
        return [IsAdminOrResponsableTier(),
                HasPermissionOrLegacy('parametres_modifier')()]

    def get_queryset(self):
        qs = super().get_queryset()
        actif = self.request.query_params.get('actif')
        if actif in ('true', '1'):
            qs = qs.filter(actif=True)
        return qs
