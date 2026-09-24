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

Un refus métier est un 400 qui NOMME son champ (``decision``, ``motif``, ou le
champ du document dont la suggestion automatique attend un humain, avec la
liste complète sous ``en_attente``) — la règle fondateur du 08/09/2026.

La société vient TOUJOURS du serveur : ``get_object()`` est borné par le
queryset du viewset, donc un calepinage d'une autre société est INTROUVABLE
(404), jamais « interdit ». Aucun montant n'apparaît ici (D-CALX 5).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuApprouverCalepinage
from ..services.approbation import (
    ApprobationRefusee, decider, etat_approbation,
)

__all__ = ['approbation']


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
        reponse = {refus.champ or 'approbation': str(refus)}
        if refus.en_attente:
            reponse['en_attente'] = refus.en_attente
        return Response(reponse, status=status.HTTP_400_BAD_REQUEST)
    return Response(etat)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.approbation = approbation
