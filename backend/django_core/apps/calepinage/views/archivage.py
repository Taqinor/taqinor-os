"""CAL208 — ``POST /calepinages/<pk>/archiver/`` et
``POST /calepinages/<pk>/restaurer-corbeille/``.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243), ``views/
bibliotheque.py`` (CAL246) et ``views/verrou.py`` (CAL207) : d'AUTRES lanes
``backend/calepinage-*`` travaillent en ce moment sur ``views/calepinages.py``
— les deux actions sont posées ICI, rattachées au ``CalepinageViewSet`` par
une ligne d'import dans ``urls.py`` (affectation d'attribut de classe).

``restaurer-corbeille`` (et non ``restaurer``, déjà pris par la restauration
de VERSION — ``versions/<id>/restaurer``, CAL20) évite toute ambiguïté entre
« revenir à un instantané de la conception » et « sortir de la corbeille ».

``self.get_object()`` N'EST PAS UTILISÉ ICI
------------------------------------------------
``get_queryset()`` du viewset (``views/calepinages.py``) passe par
``selectors.appliquer_filtres_liste``, qui EXCLUT les archivés par défaut
(CAL208) — un calepinage déjà archivé y répondrait donc 404, et
``restaurer-corbeille`` ne pourrait JAMAIS retrouver sa cible. Les deux
actions lisent donc directement ``selectors.calepinage_detail`` (borné
société, inclut les archivés) plutôt que ``self.get_object()``.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage
from ..selectors import calepinage_detail
from ..services.archivage import ArchivageInvalide, restaurer
from ..services.archivage import archiver as archiver_service

__all__ = ['archiver', 'restaurer_corbeille']


def _attacher(viewset_classe):
    viewset_classe.archiver = archiver
    viewset_classe.restaurer_corbeille = restaurer_corbeille


def _cible(request, pk):
    company = getattr(request.user, 'company', None)
    return calepinage_detail(pk, company)


@action(detail=True, methods=['post'], url_path='archiver',
        permission_classes=[PeutGererCalepinage])
def archiver(self, request, pk=None):
    """CAL208 — archive le calepinage (corbeille, réversible)."""
    calepinage = _cible(request, pk)
    if calepinage is None:
        return Response({'detail': 'Calepinage introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        archiver_service(calepinage, user=request.user)
    except ArchivageInvalide as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({'calepinage': calepinage.pk, 'archive': True})


@action(detail=True, methods=['post'], url_path='restaurer-corbeille',
        permission_classes=[PeutGererCalepinage])
def restaurer_corbeille(self, request, pk=None):
    """CAL208 — restaure le calepinage DEPUIS la corbeille, à l'identique."""
    calepinage = _cible(request, pk)
    if calepinage is None:
        return Response({'detail': 'Calepinage introuvable.'},
                        status=status.HTTP_404_NOT_FOUND)
    try:
        restaurer(calepinage, user=request.user)
    except ArchivageInvalide as refus:
        return Response({refus.champ or 'detail': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({'calepinage': calepinage.pk, 'archive': False})


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

_attacher(CalepinageViewSet)
