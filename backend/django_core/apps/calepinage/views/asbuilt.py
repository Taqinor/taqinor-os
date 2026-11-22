"""CALX366 — la pose réelle (as-built), servie en HTTP.

UNE SEULE FORME D'URL (CAL233) : ``@action`` du viewset pivot, servie sous
``/api/django/calepinage/calepinages/<pk>/pose-reelle/`` (contrat CALX337,
``contract_samples/calepinage_asbuilt_ecarts.json``). GET et POST rendent la
MÊME forme ``{source, lignes, total_prevu, total_pose, version_creee}`` :

* ``GET`` — prévu, posé et écart par pan. Garde ``calepinage_voir``.
* ``POST {pan, modules_poses, ecarts_position, releve_le}`` — enregistre (ou
  corrige) la pose d'UN pan ; 200. Garde ``calepinage_gerer``.
* ``POST {creer_version: true}`` — gèle une version des écarts par LE chemin
  unique (``services/versions.py::enregistrer_version``) ; 201 quand elle est
  créée, 200 quand les mêmes écarts étaient déjà gelés.

La garde est choisie PAR MÉTHODE (``PeutLireOuEcrireCalepinage``). Un refus
métier NOMME son champ (``pan``, ``modules_poses``, ``releve_le``,
``creer_version``) — la forme ``refus_*`` du contrat. ERR-ENF11-FUZZ-CALEPINAGE :
400 pour une saisie illisible, 404 pour un pan inconnu du document
(sous-ressource absente), 409 pour une version demandée sans aucun relevé. La
société et l'auteur viennent du serveur ; ``get_object()`` est borné par le
queryset du viewset (404 pour une autre société). Aucun statut de chantier ni
de devis ne bouge.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutApprouverCalepinage, PeutLireOuEcrireCalepinage
from ..serializers import corps_obligatoire, forme_du_contrat
from ..services.asbuilt import (
    PanInconnu, PoseRefusee, ecart_mesures_du_calepinage, enregistrer_pose,
    etat_pose_reelle, supprimer_pose, version_depuis_ecarts,
)
from .calepinages import CalepinageViewSet

__all__ = ['ecart_mesures', 'pose_reelle', 'supprimer_pose_reelle']


def _demande_de_version(corps):
    """``creer_version`` lu SANS deviner (défaut : une saisie de pan)."""
    valeur = corps.get('creer_version')
    if isinstance(valeur, bool):
        return valeur
    return str(valeur or '').strip().lower() in ('1', 'true', 'vrai', 'oui')


_FORME_POSE_REELLE = forme_du_contrat(
    'CalepinagePoseReelle', 'calepinage_asbuilt_ecarts.json')


#: ERR-ENF11-FUZZ-CALEPINAGE — le corps RÉEL (contrat ``corps_saisie`` /
#: ``corps_creer_version``) : soit la demande de version, soit la saisie d'UN
#: pan — pan désigné, entier posé >= 0, date AAAA-MM-JJ (exigée à la
#: première saisie ; le schéma l'exige toujours, la correction l'omet).
_CORPS_POSE_REELLE = {
    'type': 'object',
    'properties': {
        'creer_version': {'type': 'boolean'},
        'pan': {'type': 'string', 'pattern': r'\S'},
        'modules_poses': {'type': 'integer', 'minimum': 0,
                          'maximum': 2147483647},
        'ecarts_position': {'type': 'string'},
        'releve_le': {'type': 'string', 'format': 'date'},
    },
    'anyOf': [
        {'properties': {'creer_version': {'enum': [True]}},
         'required': ['creer_version']},
        {'required': ['pan', 'modules_poses', 'releve_le']},
    ],
}


@extend_schema(methods=['GET'], responses=_FORME_POSE_REELLE)
@extend_schema(
    methods=['POST'],
    request={'application/json': _CORPS_POSE_REELLE},
    responses={200: _FORME_POSE_REELLE, 201: _FORME_POSE_REELLE})
@corps_obligatoire
@action(detail=True, methods=['get', 'post'], url_path='pose-reelle',
        permission_classes=[PeutLireOuEcrireCalepinage])
def pose_reelle(self, request, pk=None):
    """CALX366 — lire (GET) ou saisir / figer (POST) la pose réelle."""
    calepinage = self.get_object()  # borné société par get_queryset
    if request.method.lower() != 'post':
        return Response(etat_pose_reelle(calepinage))

    corps = request.data if isinstance(request.data, dict) else None
    code = status.HTTP_200_OK
    try:
        if corps is not None and _demande_de_version(corps):
            _version, creee = version_depuis_ecarts(calepinage,
                                                    user=request.user)
            if creee:
                code = status.HTTP_201_CREATED
        else:
            enregistrer_pose(calepinage, corps, user=request.user)
    except PanInconnu as refus:
        return Response(refus.corps(), status=status.HTTP_404_NOT_FOUND)
    except PoseRefusee as refus:
        return Response(refus.corps(), status=(
            status.HTTP_409_CONFLICT if refus.champ == 'creer_version'
            else status.HTTP_400_BAD_REQUEST))
    return Response(etat_pose_reelle(calepinage), status=code)


@extend_schema(
    parameters=[OpenApiParameter(
        name='zone_id', type=OpenApiTypes.STR,
        location=OpenApiParameter.PATH,
        description='Identifiant du pan (zone) dont on retire le relevé.')],
    responses={204: None})
@action(detail=True, methods=['delete'],
        url_path=r'pose-reelle/(?P<zone_id>.+)',
        permission_classes=[PeutLireOuEcrireCalepinage])
def supprimer_pose_reelle(self, request, pk=None, zone_id=None):
    """ACAL267 — retirer le relevé d'un pan (ligne orpheline comprise).

    204 ; 404 ``{detail}`` quand aucun relevé n'est saisi pour ce pan.
    """
    calepinage = self.get_object()  # borné société par get_queryset
    try:
        supprimer_pose(calepinage, zone_id, user=request.user)
    except PoseRefusee as refus:
        return Response({'detail': str(refus)},
                        status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)


_FORME_ECART_MESURES = forme_du_contrat(
    'CalepinageEcartMesures', 'calepinage_asbuilt_mesures.json')

_CORPS_ECART_MESURES = {
    'type': 'object',
    'properties': {
        'kwh': {'type': 'array', 'minItems': 12, 'maxItems': 12,
                'items': {'type': ['number', 'null'], 'minimum': 0}},
        'annee': {'type': 'integer', 'minimum': 1900},
    },
    'required': ['kwh'],
}


@extend_schema(
    request={'application/json': _CORPS_ECART_MESURES},
    responses={200: _FORME_ECART_MESURES, 409: OpenApiTypes.OBJECT})
@action(detail=True, methods=['post'], url_path='ecart-mesures',
        permission_classes=[PeutApprouverCalepinage])
def ecart_mesures(self, request, pk=None):
    """ACAL846 — 12 consommations mesurées comparées à la simulée (rien
    d'enregistré) ; 409 nommant ``kwh[i]`` / ``annee`` illisible."""
    calepinage = self.get_object()  # borné société par get_queryset
    try:
        return Response(ecart_mesures_du_calepinage(calepinage, request.data))
    except PoseRefusee as refus:
        return Response(refus.corps(), status=status.HTTP_409_CONFLICT)


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.ecart_mesures = ecart_mesures  # ACAL846
CalepinageViewSet.pose_reelle = pose_reelle
CalepinageViewSet.supprimer_pose_reelle = supprimer_pose_reelle  # ACAL267
