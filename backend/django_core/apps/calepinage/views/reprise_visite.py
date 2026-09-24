"""CALX364 — la reprise d'une visite technique, servie en HTTP.

UNE SEULE FORME D'URL (CAL233) : ``@action`` du viewset pivot, servie sous
``/api/django/calepinage/calepinages/<pk>/releve-visite/`` (contrat CALX336,
``contract_samples/calepinage_releve_visite.json``). GET et POST partagent la
MÊME action et rendent la MÊME forme :

* ``GET`` — la dernière visite VALIDÉE du lead du calepinage, et si elle est
  déjà reprise (``deja_repris`` / ``releve``). Garde ``calepinage_voir``.
* ``POST`` — la reprend : UN ``ReleveTerrain`` de provenance ``visite``, les
  photos rattachées à leurs pièces jointes EXISTANTES. 201 quand le relevé
  vient d'être créé, 200 quand il existait déjà (rien n'est recréé). Garde
  ``calepinage_gerer``. Sans visite validée : 400 qui NOMME ``visite_id`` avec
  le motif servi par la porte de ``visites``, et RIEN n'est écrit.

L'OBJET D'ABORD (CAL29) : ``get_object()`` est borné par le queryset du
viewset, donc un calepinage d'une autre société est INTROUVABLE (404). Aucun
statut ne bouge, aucun montant n'apparaît.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage
from ..services.reprise_visite import (
    RepriseRefusee, etat_reprise, reprendre_visite,
)

__all__ = ['releve_visite']


@action(detail=True, methods=['get', 'post'], url_path='releve-visite',
        permission_classes=[PeutLireOuEcrireCalepinage])
def releve_visite(self, request, pk=None):
    """CALX364 — lire (GET) ou reprendre (POST) la visite technique validée."""
    calepinage = self.get_object()  # borné société par get_queryset
    if request.method.lower() != 'post':
        return Response(etat_reprise(calepinage))
    try:
        reponse, cree = reprendre_visite(calepinage, user=request.user)
    except RepriseRefusee as refus:
        return Response(refus.corps(), status=status.HTTP_400_BAD_REQUEST)
    return Response(reponse, status=(status.HTTP_201_CREATED if cree
                                     else status.HTTP_200_OK))


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.releve_visite = releve_visite
