"""CALX347 — la décision d'approbation, servie en HTTP.

UNE SEULE FORME D'URL (CAL233) : ``@action`` du viewset pivot, servie sous
``/api/django/calepinage/calepinages/<pk>/approbation/`` (contrat CALX334,
``contract_samples/calepinage_approbation.json``).

* ``GET`` — ``{etat, decide_par, decide_le, motif, exigee}`` ; ``etat`` vaut
  ``null`` tant que personne n'a décidé. Garde de LECTURE (``calepinage_voir``).
* ``POST`` — corps ``{decision: 'approuve'|'refuse', motif}`` ; enregistre la
  décision, écrit une note de chatter et REND l'état à jour. Garde
  ``calepinage_approuver`` : un porteur de ``calepinage_gerer`` SEUL reçoit
  403 — c'est tout l'objet du second regard.

Un refus métier NOMME son champ (``decision``, ``motif``, ou — un message par
champ — chaque valeur du document dont la suggestion automatique attend un
humain, sous son chemin ``buildings[0].hauteurM``) : la forme ``refus_*`` du
contrat, et la règle fondateur du 08/09/2026. ERR-ENF11-FUZZ-CALEPINAGE : le
corps mal formé (décision inconnue, refus sans motif) répond 400 ; un corps
bien formé que L'ÉTAT de la conception empêche (suggestion en attente,
conception vide ou bloquée, auto-approbation) répond 409, même corps.

La société vient TOUJOURS du serveur : ``get_object()`` est borné par le
queryset du viewset, donc un calepinage d'une autre société est INTROUVABLE
(404), jamais « interdit ». Aucun montant n'apparaît ici (D-CALX 5).
"""
from __future__ import annotations

from rest_framework import status
from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuApprouverCalepinage
from ..serializers import corps_obligatoire, forme_du_contrat
from ..services.approbation import (
    APPROUVE, DECISIONS, REFUSE, ApprobationRefusee, decider,
    etat_approbation,
)
from .calepinages import CalepinageViewSet

__all__ = ['approbation']


_FORME_APPROBATION = forme_du_contrat(
    'CalepinageApprobation', 'calepinage_approbation.json')


class CalepinageApprobationRequeteSerializer(drf_serializers.Serializer):
    """Le corps du POST (contrat CALX334) — schéma seulement."""

    decision = drf_serializers.ChoiceField(choices=[APPROUVE, REFUSE])
    motif = drf_serializers.CharField(required=False, allow_blank=True)


class _RefusMotivePublie(OpenApiSerializerExtension):
    """ERR-ENF11-FUZZ-CALEPINAGE — « un refus exige un motif » PUBLIÉ :
    ``{decision: 'refuse'}`` seul passait pour conforme et répondait 400.
    Énumérations ENVELOPPÉES dans les branches : le post-traitement des enums
    ne les voit pas (aucun composant renommé)."""
    target_class = CalepinageApprobationRequeteSerializer

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(
            self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        return {**schema, 'oneOf': [
            {'properties': {'decision': {'anyOf': [{'enum': [APPROUVE]}]}}},
            {'properties': {'decision': {'anyOf': [{'enum': [REFUSE]}]},
                            'motif': {'type': 'string', 'pattern': r'\S'}},
             'required': ['motif']},
        ]}


@extend_schema(methods=['GET'], responses=_FORME_APPROBATION)
@extend_schema(
    methods=['POST'], responses=_FORME_APPROBATION,
    request=CalepinageApprobationRequeteSerializer)
@corps_obligatoire
@action(detail=True, methods=['get', 'post'], url_path='approbation',
        permission_classes=[PeutLireOuApprouverCalepinage])
def approbation(self, request, pk=None):
    """CALX347 — lire (GET) ou décider (POST) l'approbation du calepinage."""
    calepinage = self.get_object()  # borné société par get_queryset
    if request.method.lower() != 'post':
        return Response(etat_approbation(calepinage))

    corps = request.data if isinstance(request.data, dict) else {}
    try:
        etat = decider(calepinage, decision=corps.get('decision'),
                       motif=corps.get('motif') or '', user=request.user)
    except ApprobationRefusee as refus:
        return Response(refus.corps(), status=_statut_du_refus(refus, corps))
    return Response(etat)


def _statut_du_refus(refus, corps):
    """400 pour un corps mal formé (décision inconnue, refus sans motif),
    409 pour un refus d'ÉTAT de la conception."""
    mal_forme = (refus.champ == 'motif'
                 or (refus.champ == 'decision'
                     and not (isinstance(corps.get('decision'), str)
                              and corps.get('decision') in DECISIONS)))
    return (status.HTTP_400_BAD_REQUEST if mal_forme
            else status.HTTP_409_CONFLICT)


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.approbation = approbation
