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
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage

__all__ = ['comparer_projets', 'comparatif_xlsx']


@action(detail=False, methods=['post'], url_path='comparer-projets',
        url_name='comparer-projets', permission_classes=[PeutVoirCalepinage])
def comparer_projets(self, request):
    """CALX341 — le comparatif de 1 à 5 calepinages de la société."""
    from ..services.comparaison_projets import (
        ComparaisonRefusee, comparer_calepinages,
    )

    corps = request.data if isinstance(request.data, dict) else {}
    try:
        return Response(comparer_calepinages(
            getattr(request.user, 'company', None), corps.get('ids')))
    except ComparaisonRefusee as refus:
        return Response({refus.champ or 'ids': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)


@action(detail=True, methods=['get'], url_path='comparatif.xlsx',
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
            getattr(request.user, 'company', None),
            [calepinage.pk] + list(autres))
        octets = exporter_comparatif_xlsx(comparaison)
    except (ComparaisonRefusee, ExportRefuse) as refus:
        return Response({getattr(refus, 'champ', '') or 'ids': str(refus)},
                        status=status.HTTP_400_BAD_REQUEST)
    return reponse_de_fichier(
        octets, mime=MIME_XLSX,
        nom_fichier='comparatif-' + nom_de_fichier(calepinage, 'xlsx'))


from .calepinages import CalepinageViewSet  # noqa: E402 — après les défs

# Le nom d'attribut est EXACTEMENT celui de la fonction : DRF mappe par
# ``__name__`` (piège CALX7 / bug de classe #105).
CalepinageViewSet.comparer_projets = comparer_projets
CalepinageViewSet.comparatif_xlsx = comparatif_xlsx
