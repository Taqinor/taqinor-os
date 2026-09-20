"""CAL207 — ``POST /calepinages/<pk>/deverrouiller/`` : lève le verrou.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243) et
``views/bibliotheque.py`` (CAL246) : d'AUTRES lanes ``backend/calepinage-*``
travaillent en ce moment sur ``views/calepinages.py`` — l'action est posée
ICI, sur son propre fichier, puis RATTACHÉE au ``CalepinageViewSet`` par une
ligne d'import dans ``urls.py`` (affectation d'attribut de classe).

Le statut du devis n'est JAMAIS touché (règle #4) — ce geste ne fait que
lever le VERROU du module lui-même, tracé au journal (CAL26). Gardé par
``calepinage_gerer`` (écriture métier), comme toute action qui modifie
l'état du pivot.
"""
from __future__ import annotations

from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from ..services.verrou import est_verrouille
from ..services.verrou import deverrouiller as deverrouiller_service
from .calepinages import CalepinageViewSet

__all__ = ['deverrouiller']


@action(detail=True, methods=['post'], url_path='deverrouiller',
        permission_classes=[PeutGererCalepinage])
def deverrouiller(self, request, pk=None):
    """CAL207 — lève le verrou (devis lié envoyé) — tracé au journal."""
    calepinage = self.get_object()
    bascule = deverrouiller_service(calepinage, user=request.user)
    return Response({'calepinage': calepinage.pk,
                     'verrouille': est_verrouille(calepinage),
                     'deverrouille': bascule})


# Rattachement au viewset PIVOT — voir la docstring du module pour le
# pourquoi de cette forme plutôt qu'une méthode inline.
CalepinageViewSet.deverrouiller = deverrouiller
