"""CAL64 — la sous-ressource « relevé terrain » du pivot.

UNE SEULE FORME D'URL (CAL233) : le relevé est une SOUS-RESSOURCE du
calepinage, donc une ``@action`` du viewset pivot
(``/api/django/calepinage/calepinages/<pk>/releve/``). Le mixin vit dans SON
fichier pour garder les lanes file-disjointes.

CE QUE L'ACTION GARANTIT
------------------------
* **L'OBJET D'ABORD (CAL29)** — ``get_object()`` précède la lecture du corps :
  un calepinage d'une autre société rend 404 quelle que soit la saisie ;
* **la société et l'auteur viennent du SERVEUR**, jamais du corps ;
* **le refus NOMME le champ** (``releve_le``, ``chaines[i]``,
  ``precision_azimut_deg``…), en français ;
* une cote DÉDUITE remonte marquée « à confirmer » — jamais une cote inventée
  en silence ;
* aucun statut ne bouge (règle #4), et le relevé n'écrit PAS le
  ``roof_layout`` : il propose une géométrie, c'est le dessinateur qui décide.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage

__all__ = ['ReleveTerrainMixin']


class ReleveTerrainMixin:
    """``GET``/``POST`` ``calepinages/<pk>/releve/`` — les relevés terrain."""

    @action(detail=True, methods=['get', 'post'], url_path='releve',
            permission_classes=[PeutLireOuEcrireCalepinage])
    def releve(self, request, pk=None):
        from ..selectors import releves_terrain
        from ..services.releve import ReleveRefuse, enregistrer_releve

        # L'OBJET D'ABORD (CAL29) : borné société par ``get_queryset``.
        calepinage = self.get_object()

        if request.method.lower() == 'get':
            return Response({'releves': releves_terrain(calepinage)})

        try:
            releve = enregistrer_releve(
                calepinage,
                request.data if isinstance(request.data, dict) else None,
                user=request.user)
        except ReleveRefuse as refus:
            return Response({refus.champ or 'detail': str(refus)},
                            status=status.HTTP_400_BAD_REQUEST)

        from ..services.releve import releve_en_ligne

        return Response({'releve': releve_en_ligne(releve),
                         'releves': releves_terrain(calepinage)},
                        status=status.HTTP_201_CREATED)
