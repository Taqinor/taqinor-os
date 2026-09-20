"""CAL144 — la porte HTTP des SORTIES du module : l'export CSV.

POURQUOI CE FICHIER EST À PART DE ``views/calepinages.py``
----------------------------------------------------------
Même raison que ``views/equipements.py`` (CAL243) : d'autres lanes
``backend/calepinage-*`` travaillent en ce moment sur ``views/calepinages.py``.
L'action est donc posée ICI, sur son propre fichier, puis RATTACHÉE au
``CalepinageViewSet`` par affectation d'attribut de classe, avec une seule
ligne d'import additive dans ``urls.py`` — qui doit s'exécuter AVANT
``router.register`` pour que le routeur découvre l'action.

CE QUE LA VUE LIT, ET CE QU'ELLE REFUSE
---------------------------------------
Elle ne calcule RIEN : elle relit le résultat DÉJÀ enregistré sur le
calepinage (``Calepinage.resultat``) et la matrice d'ombrage du document de
toiture (``roof_layout.shading12x24``, PV71). Si la série horaire n'y est pas
— cas de tout calepinage non simulé aujourd'hui — l'export est REFUSÉ avec son
motif en français et le champ nommé, jamais remplacé par un fichier de zéros.

La société est bornée par ``get_queryset`` du viewset (404 pour un calepinage
d'une autre société), comme toute autre sous-ressource.
"""
from __future__ import annotations

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from ..permissions import PeutVoirCalepinage
from ..services.export_csv import (
    EXPORTS, ExportImpossible, encoder_pour_tableur, nom_de_fichier,
)
# Renommé à l'import : l'ACTION doit s'appeler ``export_csv`` (le routeur DRF
# mappe la méthode par son ``__name__``, et l'attribut de classe doit porter
# le même nom), donc le service ne peut pas garder ce nom ici.
from ..services.export_csv import export_csv as construire_csv
from .calepinages import CalepinageViewSet

__all__ = ['document_exportable', 'export_csv']


def document_exportable(calepinage):
    """Le document d'export d'un calepinage, tel qu'il est ENREGISTRÉ.

    Aucune valeur n'est fabriquée : ce que la simulation n'a pas écrit reste
    absent, et l'exporteur refusera en le disant.
    """
    resultat = calepinage.resultat if isinstance(
        calepinage.resultat, dict) else {}
    layout = calepinage.roof_layout if isinstance(
        calepinage.roof_layout, dict) else {}
    production = resultat.get('production')
    return {
        'production': production if isinstance(production, dict) else {},
        'pertes': resultat.get('pertes') or [],
        # La série horaire est écrite par la simulation sous ``serie_horaire``
        # (liste de points {annee, mois, jour, heure, p_w, gi_w_m2, t2m_c},
        # la forme rendue par ``services.pvgis_serie``).
        'points': resultat.get('serie_horaire') or [],
        'shading12x24': layout.get('shading12x24'),
        'version_moteur': calepinage.version_moteur or None,
    }


@extend_schema(
    responses={200: OpenApiTypes.BINARY},
    parameters=[OpenApiParameter(
        name='quoi', type=OpenApiTypes.STR, required=False,
        description="Export demandé : horaire (défaut), mensuel ou ombrage.")],
)
@action(detail=True, methods=['get'], url_path='export-csv',
        permission_classes=[PeutVoirCalepinage])
def export_csv(self, request, pk=None):
    """CAL144 — ``GET /calepinages/<pk>/export-csv/?quoi=horaire``.

    * **200** — le fichier CSV (``;`` + décimale ``,`` + BOM, ouvrable tel
      quel dans Excel), précédé de son en-tête de provenance ;
    * **400** — série, agrégat mensuel ou matrice d'ombrage indisponible, ou
      export inconnu : le motif français et le champ fautif sont rendus.
    """
    calepinage = self.get_object()
    quoi = (request.query_params.get('quoi') or 'horaire').strip().lower()
    try:
        texte = construire_csv(document_exportable(calepinage),
                               quoi=quoi)
    except ExportImpossible as erreur:
        return Response({erreur.champ or 'export': [erreur.motif],
                         'exports_disponibles': list(EXPORTS)},
                        status=status.HTTP_400_BAD_REQUEST)

    reponse = HttpResponse(encoder_pour_tableur(texte),
                           content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = (
        f'attachment; filename="{nom_de_fichier(calepinage.pk, quoi)}"')
    return reponse


# Rattachement au viewset PIVOT — voir la docstring du module.
CalepinageViewSet.export_csv = export_csv
