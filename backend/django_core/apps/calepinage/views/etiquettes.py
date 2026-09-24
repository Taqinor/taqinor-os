"""CALX343 — ``GET``/``POST``/``DELETE calepinages/<pk>/etiquettes/``.

UNE SEULE URL, TROIS MÉTHODES, UNE SEULE FORME
-----------------------------------------------
Les trois méthodes rendent ``{etiquettes: [{id, nom, couleur}]}`` — la liste À
JOUR des étiquettes du calepinage (contrat
``contract_samples/calepinage_etiquettes.json``, CALX332) : l'écran n'enchaîne
jamais un second appel pour relire ce qu'il vient de poser ou de retirer.

* ``GET`` lit (garde ``calepinage_voir``) ;
* ``POST`` pose, ``DELETE`` retire (garde ``calepinage_gerer``) — le corps
  désigne l'étiquette par ``{tag_id}`` ou ``{nom}`` ; pour ``DELETE`` il est
  aussi lu dans la requête (``?tag_id=``), certains relais écartant le corps
  d'un ``DELETE``.

La garde est choisie PAR MÉTHODE (``PeutLireOuEcrireCalepinage``, CAL18) : une
garde unique mentirait d'un côté. Un refus est un 400 qui NOMME le champ
(``tag_id``, ``nom``) ; un calepinage d'une autre société est introuvable
(404, ``get_object`` borné par le queryset du viewset). Le code métier vit
dans ``services/etiquettes.py`` ; cette vue ne fait que le servir.

LA GREFFE (piège de classe #105)
---------------------------------
Posée sur le viewset pivot par AFFECTATION D'ATTRIBUT, nom d'attribut ==
``fonction.__name__`` ; l'import qui exécute ce module vit en FIN de
``views/rattachements.py``, donc AVANT ``router.register``.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage

__all__ = ['etiquettes']


def _corps(request):
    corps = request.data if isinstance(request.data, dict) else {}
    if request.method == 'DELETE' and not corps:
        params = getattr(request, 'query_params', None) or {}
        corps = {cle: params.get(cle) for cle in ('tag_id', 'nom')
                 if params.get(cle)}
    return corps


@action(detail=True, methods=['get', 'post', 'delete'],
        url_path='etiquettes', url_name='etiquettes',
        permission_classes=[PeutLireOuEcrireCalepinage])
def etiquettes(self, request, pk=None):
    """CALX343 — lire, poser ou retirer une étiquette libre."""
    from ..services.etiquettes import (
        EtiquetteRefusee, etiquettes_du_calepinage, poser_etiquette,
        retirer_etiquette,
    )

    calepinage = self.get_object()  # borné société par get_queryset
    if request.method == 'GET':
        return Response(etiquettes_du_calepinage(calepinage))
    geste = poser_etiquette if request.method == 'POST' else retirer_etiquette
    try:
        return Response(geste(calepinage, _corps(request), user=request.user))
    except EtiquetteRefusee as refus:
        return Response({refus.champ or 'tag_id': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7 / bug de classe #105).
CalepinageViewSet.etiquettes = etiquettes
