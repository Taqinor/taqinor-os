"""ACAL730 — la porte HTTP de la correspondance heure solaire / heure légale.

Action posée sur son propre fichier puis RATTACHÉE au ``CalepinageViewSet``
par affectation d'attribut de classe (même patron que ``views/export_csv.py``),
découverte par ``views/rattachements.py::MODULES_RATTACHES``. Société bornée
par ``get_object`` (404 pour un calepinage d'une autre société). Rien n'est
écrit : lecture pure d'un calcul.
"""
from __future__ import annotations

import datetime

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..serializers import REPONSE_REFUS_ETAT
from ..services.soleil_legal import SoleilLegalRefuse, correspondance_du_jour
from .calepinages import CalepinageViewSet

__all__ = ['soleil_legal']

MOTIF_DATE = "date attendue au format AAAA-MM-JJ (ex. 2026-02-11)"


def _jour(texte):
    try:
        return datetime.date.fromisoformat(str(texte or '').strip())
    except ValueError:
        return None


@extend_schema(
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT,
               409: REPONSE_REFUS_ETAT},
    parameters=[OpenApiParameter(
        name='date', type=OpenApiTypes.DATE, required=True,
        description='Le jour (AAAA-MM-JJ) dont on veut la correspondance '
                    "heure solaire vraie ↔ heure légale du site.")],
)
@action(detail=True, methods=['get'], url_path='soleil-legal',
        permission_classes=[PeutVoirCalepinage])
def soleil_legal(self, request, pk=None):
    """ACAL730 — ``GET /calepinages/<pk>/soleil-legal/?date=AAAA-MM-JJ``.

    * **200** — ``{date, fuseau, fuseau_source, longitude_deg,
      decalage_utc_min, equation_du_temps_min, ecart_legal_moins_solaire_min,
      midi_solaire_legal_h, mention}`` ;
    * **400** — ``date`` absente ou mal formée, nommée ;
    * **409** — épingle absente (``site.pin``) ou fuseau non saisi
      (``site.fuseau``) : jamais un fuseau déduit de la longitude.
    """
    calepinage = self.get_object()
    jour = _jour(request.query_params.get('date'))
    if jour is None:
        return Response({'date': [MOTIF_DATE]},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response(correspondance_du_jour(calepinage, jour))
    except SoleilLegalRefuse as refus:
        return Response({refus.champ: [refus.motif]},
                        status=status.HTTP_409_CONFLICT)


# Rattachement au viewset PIVOT : l'attribut porte EXACTEMENT le nom de la
# fonction (``get_extra_actions()`` lit ``__name__``).
CalepinageViewSet.soleil_legal = soleil_legal
