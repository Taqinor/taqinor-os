"""CALX341 — comparer jusqu'à 5 calepinages, et télécharger le comparatif.

DEUX PORTES, UNE SEULE FORME D'URL (CAL233)
--------------------------------------------
* ``POST calepinages/comparer-projets/`` — action de LISTE (``detail=False``)
  du routeur de l'objet métier : elle n'a pas d'identifiant propre, elle en
  reçoit une liste (corps ``{ids: [..]}``, de 1 à 5). La réponse est celle du
  contrat committé ``contract_samples/calepinage_comparaison_projets.json``
  (CALX331) : ``{colonnes, lignes, refus}``.
* ``GET calepinages/<pk>/comparatif.xlsx?ids=2,3`` — le MÊME comparatif en
  classeur (feuille « Comparatif », ``services/export_tableur.py``) : le
  calepinage du chemin ouvre le tableau, les ``ids`` complètent (5 au total).

CE QUI EST GARANTI
------------------
* **Société** — la société est celle de l'APPELANT, jamais lue du corps : un
  identifiant d'une autre société est IGNORÉ et listé dans ``refus`` ; le
  calepinage du chemin passe par ``get_object()`` (404 hors société).
* **Lecture pure** — POST parce qu'une liste d'identifiants n'a rien à faire
  dans une URL de liste, pas parce que quelque chose est écrit : aucune
  simulation n'est lancée, aucun statut ne bouge (d'où la garde en LECTURE,
  même patron que ``evaluer-electrique`` et ``pompage``).
* **Refus nommés** — plus de 5 identifiants, liste vide ou illisible : 400
  ``{ids: <message français>}``, jamais une erreur générique.

LA GREFFE (piège de classe #105)
---------------------------------
Les actions sont posées sur le viewset pivot par AFFECTATION D'ATTRIBUT, et le
nom de l'attribut est EXACTEMENT ``fonction.__name__`` : DRF mappe par
``__name__``. L'import qui exécute ce module vit en FIN de
``views/rattachements.py``, donc AVANT ``router.register``.
"""
from __future__ import annotations

from rest_framework import status
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core.parseurs import PARSEURS_JSON

from ..permissions import PeutVoirCalepinage
from ..serializers import forme_du_contrat
from ..services.comparaison_projets import BORNE_PROJETS
from .calepinages import CalepinageViewSet

__all__ = ['comparer_projets', 'comparatif_xlsx']


@extend_schema(request=inline_serializer(
    'CalepinageComparerProjetsRequete', {
        'ids': drf_serializers.ListField(
            child=drf_serializers.IntegerField(min_value=1),
            min_length=1, max_length=BORNE_PROJETS)}),
    responses=forme_du_contrat('CalepinageComparaisonProjets',
                               'calepinage_comparaison_projets.json'))
@action(detail=False, methods=['post'], url_path='comparer-projets',
        url_name='comparer-projets', permission_classes=[PeutVoirCalepinage],
        parser_classes=PARSEURS_JSON)  # fuzz CI #997 : liste d'ids = JSON, un multipart n'en porte que des chaînes
def comparer_projets(self, request):
    """CALX341 — le comparatif de 1 à 5 calepinages de la société."""
    from ..services.comparaison_projets import (
        ComparaisonRefusee, comparer_calepinages,
    )

    corps = request.data if isinstance(request.data, dict) else {}
    ids = corps.get('ids')
    if isinstance(ids, list) and len(ids) > BORNE_PROJETS:
        # fuzz CI #997 (2) : le schéma publie ``maxItems`` sur la liste REÇUE ;
        # six fois le même id était dédoublonné (1) puis accepté (200).
        return Response(
            {'ids': 'Au plus %d identifiants peuvent être indiqués '
                    '(reçu : %d).' % (BORNE_PROJETS, len(ids))},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        # ACAL295 — l'APPELANT, pas sa seule société : un calepinage hors de
        # sa vue tombe en refus, avec le motif d'un identifiant absent.
        return Response(comparer_calepinages(request.user, corps.get('ids')))
    except ComparaisonRefusee as refus:
        return Response({refus.champ or 'ids': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    parameters=[OpenApiParameter(
        'ids', {'type': 'array', 'items': {'type': 'integer'}},
        required=False, explode=True,
        description='Calepinages à comparer (répétable).')],
    responses={(200, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'): OpenApiTypes.BINARY})
@action(detail=True, methods=['get'], url_path=r'comparatif\.xlsx',
        url_name='comparatif-xlsx', permission_classes=[PeutVoirCalepinage])
def comparatif_xlsx(self, request, pk=None):
    """CALX341 — le comparatif en classeur ; AUCUN prix, AUCUN montant."""
    from ..services.comparaison_projets import (
        ComparaisonRefusee, comparer_calepinages,
    )
    from ..services.export_tableur import (
        ExportRefuse, exporter_comparatif_xlsx,
    )
    from ..services.planche import nom_de_fichier
    from .sorties import MIME_XLSX, reponse_de_fichier

    calepinage = self.get_object()  # borné société par get_queryset
    params = getattr(request, 'query_params', None)
    autres = params.getlist('ids') if params is not None else []
    try:
        comparaison = comparer_calepinages(
            request.user, [calepinage.pk] + list(autres))
        octets = exporter_comparatif_xlsx(comparaison)
    except (ComparaisonRefusee, ExportRefuse) as refus:
        return Response({getattr(refus, 'champ', '') or 'ids': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return reponse_de_fichier(
        octets, mime=MIME_XLSX,
        nom_fichier='comparatif-' + nom_de_fichier(calepinage, 'xlsx'))


# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7 / bug de classe #105).
CalepinageViewSet.comparer_projets = comparer_projets
CalepinageViewSet.comparatif_xlsx = comparatif_xlsx
