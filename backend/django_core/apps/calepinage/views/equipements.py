"""CAL243 — la vue ``GET /calepinages/<pk>/equipements/`` du contrat CAL120.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Deux AUTRES lanes ``backend/calepinage-*`` travaillent en ce moment sur
``views/calepinages.py`` (fichier file-disjoint par construction du plan de
lanes, ``scripts/plan_lanes.py``) : y ajouter une méthode dessus créerait un
conflit de fusion garanti. L'action est donc posée ICI, sur son propre
fichier, puis RATTACHÉE au ``CalepinageViewSet`` par une seule ligne
d'import dans ``urls.py`` (celle qui déclenche ce module) — exactement la
discipline « code dans un fichier neuf, enregistrement en ligne additive »
du plan de lanes.

Techniquement : ``@action`` doit décorer une MÉTHODE de la classe pour que
``DefaultRouter.get_extra_actions()`` (qui inspecte les attributs de la
classe au moment de ``router.register``) la découvre. On pose donc la
fonction ici puis on l'attache par affectation d'attribut de classe — le
même effet qu'une définition inline, sans toucher au corps de la classe
elle-même. L'import de ``urls.py`` doit s'exécuter AVANT
``router.register(...)`` pour que l'attribut existe déjà.
"""
from __future__ import annotations

from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services.equipements import equipements_du_calepinage
from .calepinages import CalepinageViewSet

__all__ = ['equipements']


@action(detail=True, methods=['get'], url_path='equipements',
        permission_classes=[PeutVoirCalepinage])
def equipements(self, request, pk=None):
    """CAL243 — panneau/onduleur/batterie/optimiseur retenus (contrat CAL120).

    Lecture PURE, bornée société par ``get_queryset`` (404 pour un
    calepinage d'une autre société, comme toute autre sous-ressource).
    """
    return Response(equipements_du_calepinage(self.get_object()))


# Rattachement au viewset PIVOT — voir la docstring du module pour le
# pourquoi de cette forme plutôt qu'une méthode inline.
CalepinageViewSet.equipements = equipements
