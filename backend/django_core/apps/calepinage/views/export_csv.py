"""CAL144 — la porte HTTP de l export CSV du module (fichier `views/export_csv.py`).

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

CALX7 — POURQUOI L'ACTION S'APPELLE ``export_csv_simulation``
--------------------------------------------------------------
``SortiesMixin`` (``views/sorties.py``) porte DÉJÀ une action ``export_csv``
(``url_path='export.csv'``, CAL179 — modules, chaînes et nomenclature). Tant
que ce fichier posait ``CalepinageViewSet.export_csv``, l'attribut de classe
ÉCRASAIT celle du mixin : ``get_extra_actions()`` n'en voyait qu'UNE, et
l'export tableur — pourtant construit et testé — n'était jamais enregistré.
Les deux actions portent donc des noms distincts :

* ``export_csv``            → ``export.csv``  (CAL179, tableur, le mixin) ;
* ``export_csv_simulation`` → ``export-csv``  (CAL144, ce fichier).

Le nom de la fonction, celui de l'attribut de classe et la clé du mapping DRF
doivent rester IDENTIQUES (``get_extra_actions()`` lit ``__name__``) : aucun
alias, aucun décorateur qui ne recopierait pas ``__name__``. ``url_path``
reste ``export-csv`` — aucune URL publique ne change de forme. Le ``url_name``
n'est pas épinglé ici : DRF le dérive du nom de la méthode
(``export-csv-simulation``), ce qui laisse à l'export tableur du mixin son
propre ``url_name='export-csv'``. Épingler les deux sur le même ``url_name``
rendrait l'un des deux irréversible — ``reverse()`` ne rend que le DERNIER
motif enregistré sous un nom donné.
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
# Renommé à l'import : le service ``export_csv`` et l'action HTTP vivent dans
# le même espace de noms, ils ne peuvent pas porter le même nom ici.
from ..services.export_csv import export_csv as construire_csv
from .calepinages import CalepinageViewSet

__all__ = ['document_exportable', 'export_csv_simulation']


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
def export_csv_simulation(self, request, pk=None):
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


# Rattachement au viewset PIVOT — voir la docstring du module. CALX7 :
# l'attribut porte EXACTEMENT le nom de la fonction, sinon
# ``get_extra_actions()`` ignore l'action ; et il ne masque plus
# ``SortiesMixin.export_csv`` (``export.csv``, CAL179).
CalepinageViewSet.export_csv_simulation = export_csv_simulation
