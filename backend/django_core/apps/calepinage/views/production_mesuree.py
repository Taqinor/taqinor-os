"""ACAL887 — ``GET``/``PUT calepinages/<pk>/production-mesuree/``.

Contrat ``contract_samples/calepinage_production_mesuree.json`` (ACAL886).
Greffée sur ``CalepinageViewSet`` (import en fin de ``views/rattachements.py``).
``GET`` rend les mesures rangées et leur écart au P50 mensuel servi ; ``PUT``
range ``{annee, mesures: [{mois, kwh_mesure}]}`` (au plus 12 lignes, un mois
une fois). Un refus nomme son champ (400). La société et l'auteur viennent du
serveur (``get_object()`` est borné par le queryset : 404 pour une autre
société). Droit : ceux du module (``PeutLireOuEcrireCalepinage``) — la donnée
n'est ni un prix ni un secret. Aucun statut ne bouge, aucune alerte, aucun
seuil : l'écart est publié, pas jugé.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from ..permissions import PeutLireOuEcrireCalepinage
from ..serializers import corps_obligatoire, forme_du_contrat
from ..services.production_mesuree import (
    MesureRefusee, enregistrer_mesures, etat_production_mesuree,
)
from .calepinages import CalepinageViewSet

__all__ = ['production_mesuree']

_FORME = forme_du_contrat('CalepinageProductionMesuree',
                          'calepinage_production_mesuree.json')

#: Le corps RÉEL du PUT (contrat ``exemple_corps``).
_CORPS_MESURES = {
    'type': 'object',
    'required': ['annee', 'mesures'],
    'properties': {
        'annee': {'type': 'integer', 'minimum': 1900, 'maximum': 32767},
        'mesures': {'type': 'array', 'maxItems': 12, 'items': {
            'type': 'object', 'required': ['mois', 'kwh_mesure'],
            'properties': {
                'mois': {'type': 'integer', 'minimum': 1, 'maximum': 12},
                'kwh_mesure': {'type': 'number', 'minimum': 0}}}},
    },
}


@extend_schema(methods=['GET'], responses=_FORME)
@extend_schema(
    methods=['PUT'],
    request={'application/json': _CORPS_MESURES},
    responses={200: _FORME, 400: OpenApiResponse(description=(
        "Mesure refusée : corps ``{champ: [message]}`` nommant le champ "
        "(année, mois hors bornes, kWh illisible).")),
        409: OpenApiResponse(description=(
            "Un mois saisi deux fois (règle liant plusieurs lignes) : "
            "``{mesures[i].mois: [message]}``."))})
@corps_obligatoire
@action(detail=True, methods=['get', 'put'], url_path='production-mesuree',
        permission_classes=[PeutLireOuEcrireCalepinage])
def production_mesuree(self, request, pk=None):
    """ACAL887 — lire (GET) ou ranger (PUT) les douze kWh mensuels mesurés."""
    calepinage = self.get_object()  # borné société par get_queryset
    if request.method.lower() == 'put':
        try:
            enregistrer_mesures(calepinage, request.data, user=request.user)
        except MesureRefusee as refus:
            return Response(refus.corps(), status=refus.statut)
    return Response(etat_production_mesuree(calepinage))


# Le nom d