"""CALX345 — ``GET calepinages/<pk>/versions/<version_id>/diff/?contre=<id>``.

Le différentiel champ par champ entre deux versions d'UN calepinage (contrat
``contract_samples/calepinage_versions_diff.json``, CALX333), calculé par
``services/diff_versions.py::comparer_versions`` — LECTURE PURE : rien n'est
écrit, aucune version n'est créée.

* ``gauche`` = la version du chemin ; ``droite`` = la version ``contre`` —
  ou, sans ``contre``, l'ÉTAT COURANT du calepinage (``id: null``) ;
* une version d'un AUTRE calepinage (donc aussi d'une autre société) est
  INTROUVABLE : 404, pour la version du chemin comme pour ``contre`` — les
  deux sont cherchées dans ``selectors.versions(calepinage)``, et le
  calepinage lui-même passe par ``get_object()`` (404 hors société) ;
* un ``contre`` non entier est refusé 400 en NOMMANT le champ.

LA GREFFE (piège de classe #105)
---------------------------------
Posée sur le viewset pivot par AFFECTATION D'ATTRIBUT, nom d'attribut ==
``fonction.__name__`` ; l'import qui exécute ce module vit en FIN de
``views/rattachements.py``, donc AVANT ``router.register``. Le chemin est une
sous-route de ``versions/<version_id>/`` — même forme que ``restaurer``
(``views/calepinages.py``), sans ``/`` de tête.
"""
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage

__all__ = ['versions_diff']

INTROUVABLE = 'Version introuvable.'


def _identifiant(brut):
    texte = str(brut or '').strip()
    return int(texte) if texte.isdigit() and int(texte) > 0 else None


# Le paramètre de chemin ``version_id`` n'est pas un champ du modèle pivot :
# sans cette déclaration, drf-spectacular ne sait pas le typer (même
# déclaration que ``restaurer``, ``views/calepinages.py``).
@extend_schema(parameters=[
    OpenApiParameter(name='version_id', type=OpenApiTypes.INT,
                     location=OpenApiParameter.PATH,
                     description="L'identifiant de la version de gauche."),
    OpenApiParameter(name='contre', type=OpenApiTypes.INT,
                     location=OpenApiParameter.QUERY, required=False,
                     description=("La version de droite ; absente, l'état "
                                  'courant du calepinage.')),
])
@action(detail=True, methods=['get'],
        url_path=r'versions/(?P<version_id>[^/.]+)/diff',
        url_name='versions-diff', permission_classes=[PeutVoirCalepinage])
def versions_diff(self, request, pk=None, version_id=None):
    """CALX345 — les écarts entre deux versions (ou une version et l'état
    courant), bornés aux grandeurs comptables du document."""
    from .. import selectors
    from ..services.diff_versions import comparer_versions, etat_courant

    calepinage = self.get_object()  # borné société par get_queryset
    historique = selectors.versions(calepinage)
    ident = _identifiant(version_id)
    gauche = historique.filter(pk=ident).first() if ident else None
    if gauche is None:
        return Response({'detail': INTROUVABLE},
                        status=status.HTTP_404_NOT_FOUND)

    params = getattr(request, 'query_params', None) or {}
    brut = params.get('contre')
    if brut in (None, ''):
        droite = etat_courant(calepinage)
    else:
        contre = _identifiant(brut)
        if contre is None:
            return Response(
                {'contre': ("Le paramètre « contre » attend l'identifiant "
                            "d'une version (reçu : « %s »)." % brut)},
                status=status.HTTP_400_BAD_REQUEST)
        droite = historique.filter(pk=contre).first()
        if droite is None:
            return Response({'detail': INTROUVABLE},
                            status=status.HTTP_404_NOT_FOUND)
    return Response(comparer_versions(gauche, droite))


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7 / bug de classe #105).
CalepinageViewSet.versions_diff = versions_diff
