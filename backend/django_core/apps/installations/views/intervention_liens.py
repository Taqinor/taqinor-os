"""APUB6 — coupure du lien public du compte-rendu d'intervention, sortie de
``intervention.py`` (fichier ≥ 2 000 lignes, C20)."""
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.roles.permissions import DroitDeLaGrille
from authentication.permissions import IsResponsableOrAdmin

from . import _openapi as oa


class CouperLienRapportMixin:
    @oa.extend_schema(request=None, responses=oa.OBJ)
    @action(detail=True, methods=['post'], url_path='couper-lien-rapport',
            permission_classes=[IsResponsableOrAdmin, DroitDeLaGrille('intervention_gerer')])  # ADRG79
    def couper_lien_rapport(self, request, pk=None):
        """APUB6 — coupe le lien public du compte-rendu : page, PDF et photos
        rendent 404 sur l'ancien jeton ; ``lien-rapport`` en pose un neuf."""
        interv = self.get_object()
        interv.couper_lien_rapport()
        return Response({'coupe': True})
