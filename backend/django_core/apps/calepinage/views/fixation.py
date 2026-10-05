"""CALX359 — la nomenclature de fixation, servie en HTTP.

UNE SEULE FORME D'URL (CAL233) : ``@action`` du viewset pivot, servie sous
``/api/django/calepinage/calepinages/<pk>/bom-fixation/`` — contrat CALX335
(``contract_samples/calepinage_fixation_bom.json``). La réponse est la
sortie de ``services/fixation.py::bom_de_fixation`` MOT POUR MOT :
aucune clé n'est ajoutée ni reformulée ici.

``?systeme=<id>`` désigne le système du catalogue de la société ; à défaut,
l'UNIQUE système actif est appliqué. Un système introuvable, un catalogue
vide ou plusieurs systèmes actifs sans choix sont DITS dans ``refus`` (le
champ ``systeme`` y est nommé), jamais devinés.

Lecture PURE : aucun statut ne bouge, aucun document n'est écrit, aucun
montant n'apparaît (D5). La société vient TOUJOURS du serveur :
``get_object()`` est borné par le queryset du viewset, donc un calepinage
d'une autre société est INTROUVABLE (404), et le système est lu borné à la
société du calepinage.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutGererCalepinage, PeutVoirCalepinage
from ..services.fixation import (
    FixationRefusee, appliquer_systeme, bom_de_fixation,
    resoudre_systeme_et_source,
)

__all__ = ['bom_fixation', 'fixation']


@action(detail=True, methods=['get'], url_path='bom-fixation',
        url_name='bom-fixation', permission_classes=[PeutVoirCalepinage])
def bom_fixation(self, request, pk=None):
    """CALX359 — ``{systeme, lignes, refus, systeme_source}`` (CALX335).

    ACAL81 — sans ``?systeme=``, le système CHOISI sur le calepinage est lu
    avant l'unique système actif.
    """
    calepinage = self.get_object()  # borné société par get_queryset
    systeme, refus, source = resoudre_systeme_et_source(
        calepinage.company, request.query_params.get('systeme'),
        calepinage=calepinage)
    return Response(bom_de_fixation(calepinage, systeme, refus, source))


@action(detail=True, methods=['post'], url_path='fixation',
        url_name='fixation', permission_classes=[PeutGererCalepinage])
def fixation(self, request, pk=None):
    """ACAL81 — ``{systeme_id|null}`` → ``{systeme, systeme_source}``.

    Persiste le système de fixation choisi (``null`` l'efface). Un id absent
    ou d'une autre société : le MÊME 400, champ ``systeme_id`` nommé.
    """
    calepinage = self.get_object()  # borné société par get_queryset
    corps = request.data if isinstance(request.data, dict) else {}
    if 'systeme_id' not in corps:
        return Response(
            {'systeme_id': "Indiquez le système de fixation à appliquer "
                           "(ou null pour retirer le choix)."},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        reponse = appliquer_systeme(calepinage, corps.get('systeme_id'))
    except FixationRefusee as refus:
        return Response({refus.champ: str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response(reponse)


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.bom_fixation = bom_fixation
CalepinageViewSet.fixation = fixation  # ACAL81
