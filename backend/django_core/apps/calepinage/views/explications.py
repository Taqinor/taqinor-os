"""ACAL871 — ``GET calepinages/explications/`` : le registre des phrases.

Action de LISTE (sans ``pk``), lecture pure d'une donnée versionnée
(``data/explications.json``) : aucune donnée d'une société, donc lisible par
tout utilisateur qui voit le module. Code métier : ``services/explications.py``.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services.explications import charger_explications
from .calepinages import CalepinageViewSet

__all__ = ['explications']


@extend_schema(responses=forme_du_contrat(
    'CalepinageExplications', 'calepinage_explications.json'))
@action(detail=False, methods=['get'], url_path='explications',
        url_name='explications', permission_classes=[PeutVoirCalepinage])
def explications(self, request):
    """ACAL871 — le registre ``{entrees: [...]}``, trié par famille et clé."""
    return Response(charger_explications())


# Le nom d'attribut est EXACTEMENT celui de la fonction (piège CALX7).
CalepinageViewSet.explications = explications
