"""CAL246 — ``GET /calepinages/modeles/`` : les calepinages MARQUÉS modèle.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
------------------------------------------------------------
Même discipline que ``views/equipements.py`` (CAL243) : d'AUTRES lanes
``backend/calepinage-*`` travaillent en ce moment sur ``views/calepinages.py``
(file-disjoint par construction du plan de lanes) — y ajouter une méthode
créerait un conflit de fusion garanti. L'action est donc posée ICI, sur son
propre fichier, puis RATTACHÉE au ``CalepinageViewSet`` par une ligne
d'import dans ``urls.py`` (affectation d'attribut de classe — le même effet
qu'une définition inline, sans toucher au corps de la classe).

LA BIBLIOTHÈQUE (CAL197-CAL200), EN DEUX ENDROITS — JAMAIS UNE TROISIÈME
FORME D'URL (CAL233)
--------------------------------------------------------------------------
* ``GET /api/django/calepinage/parametres/`` sert DÉJÀ les presets et le
  matériel favori (sections de ``ParametresCalepinage``, CAL45/CAL16) — ce
  module y AJOUTE ``kits`` (catalogue LU, jamais stocké : voir
  ``views/parametres.py``) ;
* ``GET /api/django/calepinage/calepinages/modeles/`` (CETTE action, sur le
  routeur DRF de l'objet métier — ``detail=False``, donc pas de second
  préfixe d'URL) sert les calepinages marqués MODÈLE (CAL199).

Lecture PURE, bornée société par ``get_queryset``/``self.request.user`` comme
toute autre action du viewset — écriture gardée par ``calepinage_gerer``
ailleurs (marquer/démarquer, action de ``services.modeles``).
"""
from __future__ import annotations

from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..serializers import CalepinageSerializer
from ..services.modeles import calepinages_modeles
from .calepinages import CalepinageViewSet

__all__ = ['modeles']


@action(detail=False, methods=['get'], url_path='modeles',
        permission_classes=[PeutVoirCalepinage])
def modeles(self, request):
    """CAL199/CAL246 — les calepinages marqués « modèle » de la société.

    Lecture PURE, bornée société (``request.user.company`` — jamais un corps
    de requête)."""
    company = getattr(request.user, 'company', None)
    lignes = calepinages_modeles(company)
    return Response(CalepinageSerializer(lignes, many=True).data)


# Rattachement au viewset PIVOT — voir la docstring du module pour le
# pourquoi de cette forme plutôt qu'une méthode inline.
CalepinageViewSet.modeles = modeles
