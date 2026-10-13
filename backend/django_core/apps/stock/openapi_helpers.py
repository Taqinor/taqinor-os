"""ENF4 — petits assistants pour déclarer EXACTEMENT le schéma OpenAPI des
vues stock/achats (statuts, corps, paramètres de requête, exports binaires).

Aucune logique métier : uniquement des constructeurs drf-spectacular, pour que
chaque ``@extend_schema`` reste sur une ligne lisible.
"""
from typing import Any, Dict, List

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.openapi import AutoSchema
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


def P(name, typ=STR, required=False, desc='', enum=None, mini=None, maxi=None, pattern=None):
    """Paramètre de requête (query string) ; ``mini``/``maxi`` bornent un entier."""
    if typ == STR and pattern is not None:
        typ = {'type': 'string', 'pattern': pattern}
    if typ == INT and (mini is not None or maxi is not None):
        typ = {'type': 'integer', **({'minimum': mini} if mini is not None else {}),
               **({'maximum': maxi} if maxi is not None else {})}
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


class SchemaObjetUnique(AutoSchema):
    """Singleton exposé par ``list`` (un OBJET, pas un tableau) : sans cela
    drf-spectacular enveloppe la réponse du ``list`` dans un tableau (ENF11)."""

    def _is_list_view(self, serializer=None):
        return False


class EntierBornePublie(serializers.IntegerField):
    """Entier dont la borne (``min_value``/``max_value``) est PUBLIÉE au schéma
    (api-fuzz « rejected schema-compliant ») mais CONTRÔLÉE par le
    ``validate_<champ>`` du sérialiseur : le contrat d'erreur (message
    français, code ``invalid``) reste celui que les contrats WMS épinglent."""

    def __init__(self, borne_validee, **kwargs):
        """``borne_validee`` : ``'min'`` ou ``'max'`` — la seule borne dont le
        validateur DRF est retiré (l'autre reste contrôlée par DRF)."""
        from django.core.validators import MaxValueValidator, MinValueValidator
        super().__init__(**kwargs)
        classe = MinValueValidator if borne_validee == 'min' else MaxValueValidator
        self.validators = [v for v in self.validators if not isinstance(v, classe)]


class _EmplacementTiersNomme(OpenApiSerializerExtension):
    """ERR fuzz (PUT/POST emplacements) — règle croisée PUBLIÉE au schéma de
    requête : un emplacement non interne nomme son tiers (``tiers_nom`` non
    blanc), sinon 400 « Nommez le tiers… » sur un corps jugé conforme. Le
    PATCH (partiel, type relu sur l'instance) garde le schéma brut."""
    target_class = 'apps.stock.serializers.EmplacementStockSerializer'

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(self.target, direction, bypass_extensions=True)
        if direction != 'request' or auto_schema.method == 'PATCH':
            return schema
        from .models import EmplacementStock
        interne = EmplacementStock.TypeProprietaire.INTERNE
        tiers = [v for v in EmplacementStock.TypeProprietaire.values if v != interne]
        # Enums ENVELOPPÉS (``anyOf`` de propriété) : le post-traitement des
        # enums de drf-spectacular ne les voit pas — sinon il renomme le
        # composant ``TypeProprietaireEnum`` (collision de jeux de valeurs).
        return {**schema, 'anyOf': [
            {'properties': {'type_proprietaire': {'anyOf': [{'enum': [interne]}]}}},
            {'properties': {'type_proprietaire': {'anyOf': [{'enum': tiers}]},
                            'tiers_nom': {'type': 'string', 'pattern': r'\S'}},
             'required': ['type_proprietaire', 'tiers_nom']},
        ]}


class _BudgetPeriodeCoherente(OpenApiSerializerExtension):
    """ERR fuzz (POST/PUT budgets-departement) — règle croisée PUBLIÉE : un
    budget mensuel porte un mois 1-12, un budget annuel le mois 0 (ou rien) ;
    le montant alloué n'est jamais négatif. Sinon des corps « conformes »
    étaient refusés en 400. Enums enveloppés : voir ``_EmplacementTiersNomme``."""
    target_class = 'apps.stock.views.budget_departement.BudgetDepartementSerializer'

    def map_serializer(self, auto_schema, direction):
        schema = auto_schema._map_serializer(self.target, direction, bypass_extensions=True)
        if direction != 'request':
            return schema
        montant = dict(schema['properties']['montant_alloue'])
        montant['pattern'] = montant['pattern'].replace('^-?', '^', 1)
        branches = [
            {'properties': {'periodicite': {'anyOf': [{'enum': ['mensuelle']}]},
                            'mois': {'minimum': 1, 'maximum': 12}},
             'required': ['periodicite', 'mois']},
            {'properties': {'periodicite': {'anyOf': [{'enum': ['annuelle']}]},
                            'mois': {'maximum': 0}}},
        ]
        if auto_schema.method == 'PATCH':
            # Partiel : la période est relue sur l'instance — on n'annonce que
            # les corps que la vue accepte QUEL QUE SOIT l'état (période ET
            # mois cohérents, période annuelle seule, ou ni l'une ni l'autre).
            branches[1]['required'] = ['periodicite']
            branches.append({'not': {'anyOf': [{'required': ['periodicite']}, {'required': ['mois']}]}})
        return {**schema, 'properties': {**schema['properties'], 'montant_alloue': montant}, 'anyOf': branches}
