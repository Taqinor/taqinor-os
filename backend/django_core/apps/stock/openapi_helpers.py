"""ENF4 — petits assistants pour déclarer EXACTEMENT le schéma OpenAPI des
vues stock/achats (statuts, corps, paramètres de requête, exports binaires).

Aucune logique métier : uniquement des constructeurs drf-spectacular, pour que
chaque ``@extend_schema`` reste sur une ligne lisible.
"""
from typing import Any, Dict, List

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, inline_serializer
from rest_framework import serializers

STR = OpenApiTypes.STR
INT = OpenApiTypes.INT
BOOL = OpenApiTypes.BOOL
DATE = OpenApiTypes.DATE
NUM = OpenApiTypes.NUMBER
BINARY = OpenApiTypes.BINARY
OBJET = OpenApiTypes.OBJECT

# Liste d'objets libres (rapports dont la forme n'a pas de sérialiseur).
LISTE = List[Dict[str, Any]]

PDF = (200, 'application/pdf')
XLSX = (
    200,
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
)
CSV = (200, 'text/csv')


def P(name, typ=STR, required=False, desc='', enum=None):
    """Paramètre de requête (query string)."""
    return OpenApiParameter(
        name=name, type=typ, location=OpenApiParameter.QUERY,
        required=required, description=desc or name, enum=enum)


PID = OpenApiParameter(
    name='id', type=INT, location=OpenApiParameter.PATH, description='Identifiant')
PTOKEN = OpenApiParameter(
    name='token_id', type=INT, location=OpenApiParameter.PATH,
    description='Identifiant du jeton')


def corps(_nom, /, **champs):
    """Corps de requête / réponse inline. ``champs`` : ``nom=serializers.X``."""
    return inline_serializer(name=_nom, fields=champs)


def detail_reponse(nom='DetailReponse'):
    return corps(nom, detail=serializers.CharField())
