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

from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services.fixation import bom_de_fixation, resoudre_systeme

__all__ = ['bom_fixation']


@action(detail=True, methods=['get'], url_path='bom-fixation',
        url_name='bom-fixation', permission_classes=[PeutVoirCalepinage])
def bom_fixation(self, request, pk=None):
    """CALX359 — ``{systeme, lignes, refus}`` (contrat CALX335)."""
    calepinage = self.get_object()  # borné société par get_queryset
    systeme, refus = resoudre_systeme(calepinage.company,
                                      request.query_params.get('systeme'))
    return Response(bom_de_fixation(calepinage, systeme, refus))


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7).
CalepinageViewSet.bom_fixation = bom_fixation
