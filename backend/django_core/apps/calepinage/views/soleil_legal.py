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
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..serializers import REPONSE_REFUS_ETAT, forme_du_contrat
from ..services.soleil_legal import (
    MOTIF_SANS_EPINGLE, SoleilLegalRefuse, correspondance_du_jour,
)
from .calepinages import CalepinageViewSet

__all__ = ['soleil_legal']

MOTIF_DATE = "date attendue au format AAAA-MM-JJ (ex. 2026-02-11)"


def _jour(texte):
    try:
        return datetime.date.fromisoformat(str(texte or '').strip())
    except ValueError:
        return None


@extend_schema(
    responses={200: forme_du_contrat('CalepinageSoleilLegal',
                                     'calepinage_soleil_legal.json'),
               400: OpenApiResponse(description="« date » absente ou mal "
                                                "formée, nommée ({date: [message]})."),
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
    * **200 sans heure** — ``{date, absence: {champ: 'site.pin', motif}}`` : aucune position
      du site (ni épingle, ni ville du lead ou du client). C'est un état du dossier que
      l'écran ne peut pas deviner avant de demander (ENF11 : 409 seulement quand l'appelant
      pouvait savoir) : l'absence est DITE, sans refus, donc sans erreur à chaque ouverture ;
    * **409** — fuseau non saisi (``site.fuseau``) : jamais un fuseau déduit de la longitude.
    """
    calepinage = self.get_object()
    jour = _jour(request.query_params.get('date'))
    if jour is None:
        return Response({'date': [MOTIF_DATE]},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response(correspondance_du_jour(calepinage, jour))
    except SoleilLegalRefuse as refus:
        if refus.champ == 'site.pin' and refus.motif == MOTIF_SANS_EPINGLE:
            # T4-U4-018 — aucune position du site : l'absence est servie (200), pas refusée.
            return Response({'date': jour.isoformat(),
                             'absence': {'champ': refus.champ, 'motif': refus.motif}})
        return Response({refus.champ: [refus.motif]},
                        status=status.HTTP_409_CONFLICT)


# Rattachement au viewset PIVOT : l'attribut porte EXACTEMENT le nom de la
# fonction (``get_extra_actions()`` lit ``__name__``).
CalepinageViewSet.soleil_legal = soleil_legal
