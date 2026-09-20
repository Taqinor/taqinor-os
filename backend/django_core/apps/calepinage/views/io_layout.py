"""CAL216 — ``GET .../export-layout/`` et ``POST .../import-layout/``.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243), ``views/
bibliotheque.py`` (CAL246), ``views/verrou.py`` (CAL207) et ``views/
archivage.py`` (CAL208) : les deux actions sont posées ICI, rattachées au
``CalepinageViewSet`` par une ligne d'import dans ``urls.py`` (affectation
d'attribut de classe).

``self.get_object()`` PEUT être utilisé ici (contrairement à CAL208) : un
calepinage archivé n'a aucune raison d'être importé/exporté — le 404 par
défaut du viewset est le bon comportement.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutLireOuEcrireCalepinage
from ..services.io_layout import (
    ImportLayoutRefuse, exporter_layout, importer_layout,
)
from ..services.layout import LayoutRefuse

# Les ACTIONS portent EXACTEMENT le nom de leur attribut de classe : le
# routeur DRF (``get_extra_actions``) refuse toute fonction dont le
# ``__name__`` diffère, et l'import d'``urls.py`` échouait alors entièrement.
__all__ = ['export_layout', 'import_layout']


def _attacher(viewset_classe):
    viewset_classe.export_layout = export_layout
    viewset_classe.import_layout = import_layout


@action(detail=True, methods=['get'], url_path='export-layout',
        permission_classes=[PeutLireOuEcrireCalepinage])
def export_layout(self, request, pk=None):
    """CAL216 — exporte ``roof_layout`` TEL QUEL."""
    calepinage = self.get_object()
    return Response(exporter_layout(calepinage))


@action(detail=True, methods=['post'], url_path='import-layout',
        permission_classes=[PeutLireOuEcrireCalepinage])
def import_layout(self, request, pk=None):
    """CAL216 — importe un document ``roof_layout``, validé STRICTEMENT
    contre le schéma v2 avant écriture — refus 400 champ par champ."""
    calepinage = self.get_object()
    corps = request.data
    if isinstance(corps, dict) and set(corps.keys()) == {'roof_layout'}:
        corps = corps['roof_layout']
    try:
        resultat = importer_layout(calepinage, corps, user=request.user)
    except (ImportLayoutRefuse, LayoutRefuse) as refus:
        return Response({refus.champ or 'roof_layout': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({
        'calepinage': calepinage.pk,
        'layout_hash': resultat['layout_hash'],
        'inchange': resultat['inchange'],
    })


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

_attacher(CalepinageViewSet)
