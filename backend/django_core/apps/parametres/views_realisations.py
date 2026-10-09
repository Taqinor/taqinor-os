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
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.parsers import JSONParser

from authentication.permissions import (
    HasPermissionOrLegacy, IsAdminOrResponsableTier, IsAnyRole,
)
from core.viewsets import CompanyScopedModelViewSet

from .models_realisations import Realisation
from .serializers_realisations import RealisationSerializer
from .views_common import ACTIF_PARAM, SettingsAuditedMixin

READ_ACTIONS = ['list', 'retrieve']


@extend_schema_view(list=extend_schema(parameters=[ACTIF_PARAM]))
class RealisationViewSet(SettingsAuditedMixin, CompanyScopedModelViewSet):
    """Catalogue des installations réelles de la société. ``?actif=true``.

    APAR28 — chaque écriture est journalisée (``SettingsAuditedMixin``)."""

    queryset = Realisation.objects.all()
    serializer_class = RealisationSerializer
    audit_section = 'realisations'
    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
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
