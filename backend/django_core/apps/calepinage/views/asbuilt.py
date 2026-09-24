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
métier est un 400 qui NOMME son champ (``pan``, ``modules_poses``,
``releve_le``, ``creer_version``) — la forme ``refus_*`` du contrat. La
société et l'auteur viennent du serveur ; ``get_object()`` est borné par le
queryset du viewset (404 pour une autre société). Aucun statut de chantier ni
de devis ne bouge.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage
from ..services.asbuilt import (
    PoseRefusee, enregistrer_pose, etat_pose_reelle, version_depuis_ecarts,
)

__all__ = ['pose_reelle']


def _demande_de_version(corps):
    """``creer_version`` lu SANS deviner (défaut : une saisie de pan)."""
    valeur = corps.get('creer_version')
    if isinstance(valeur, bool):
        return valeur
    return str(valeur or '').strip().lower() in ('1', 'true', 'vrai', 'oui')


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
    except PoseRefusee as refus:
        return Response(refus.corps(), status=status.HTTP_400_BAD_REQUEST)
    return Response(etat_pose_reelle(calepinage), status=code)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.pose_reelle = pose_reelle
