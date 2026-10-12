"""NTDATA33 — drill-down : d'une cellule de pivot jusqu'aux enregistrements.

``POST core/data-explorer/drill/`` prend le dataset + les VALEURS de group_by de
la cellule cliquée (« 12 devis en Mars ») et renvoie les identifiants
sous-jacents accompagnés d'un LIEN PROFOND vers l'écran détail de l'app
propriétaire.

Deux garde-fous, aucun contournement :

* la liste blanche du dataset (``core.data_explorer``) valide chaque champ de
  regroupement — impossible de forer sur un champ non exposé ;
* le queryset du dataset est DÉJÀ borné à la société par l'app propriétaire :
  le drill-down ne peut pas sortir du périmètre de l'utilisateur.

La table de correspondance dataset → route détail vit dans
``core.dashboard_data.register_drill`` : c'est l'APP qui déclare sa route,
``core`` n'en connaît aucune en dur (contrat import-linter).

``GET`` sur la même URL renvoie le catalogue des mappings — de quoi savoir,
côté front, quels widgets sont forables.
"""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAnyRole

from . import dashboard_data, data_explorer
from .champs_stricts import ChaineStricte
from .parseurs import corps_valide

__all__ = ['DrillDownView', 'LIMITE_MAX_LIGNES']

#: Borne dure du drill-down (une liste cliquable, jamais un export déguisé).
LIMITE_MAX_LIGNES = 1000
#: Nombre d'enregistrements renvoyés par défaut.
LIMITE_DEFAUT = 200


# ERR-ENF11-FUZZ-CORE — corps validé par ce serializer DÉCLARÉ : un
# ``dataset`` non texte levait une erreur de hachage (500). ``limite`` est
# bornée au schéma comme dans ``dashboard_data.drill`` (1..LIMITE_MAX_LIGNES).
_REQUETE_DRILL = inline_serializer('DrillRequete', {
    'dataset': ChaineStricte(),
    'group_by': drf_serializers.DictField(required=False),
    'filtres': drf_serializers.DictField(required=False),
    'limite': drf_serializers.IntegerField(
        required=False, min_value=1, max_value=LIMITE_MAX_LIGNES),
})


class DrillDownView(APIView):
    """Enregistrements sous-jacents d'un point de graphe / d'une cellule."""

    parser_classes = [JSONParser]  # ENF8 (D2) — aucun upload
    permission_classes = [IsAnyRole]

    @extend_schema(
        responses=inline_serializer('DrillCatalogueReponse', {
            'mappings': drf_serializers.JSONField(),
        }))
    def get(self, request):
        """Catalogue des datasets forables (dataset → champ id + route)."""
        return Response({'mappings': dashboard_data.list_drill()})

    @extend_schema(
        request=_REQUETE_DRILL,
        responses=inline_serializer('DrillReponse', {
            'dataset': drf_serializers.CharField(),
            'id_field': drf_serializers.CharField(),
            'route': drf_serializers.CharField(),
            'nb': drf_serializers.IntegerField(),
            'enregistrements': drf_serializers.JSONField(),
        }))
    def post(self, request):
        corps = corps_valide(request, _REQUETE_DRILL)
        dataset = corps['dataset']
        group_by = corps.get('group_by') or {}
        filtres = corps.get('filtres') or {}
        try:
            resultat = dashboard_data.drill(
                dataset, request.user.company, request.user,
                group_by=group_by, filters=filtres,
                limit=corps.get('limite') or LIMITE_DEFAUT)
        except data_explorer.DatasetInconnu as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)
        except data_explorer.ChampNonAutorise as exc:
            return Response({'detail': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(resultat)
