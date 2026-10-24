import functools
"""ENF4 — petits assistants pour déclarer EXACTEMENT le schéma OpenAPI des
vues stock/achats (statuts, corps, paramètres de requête, exports binaires).

Aucune logique métier : uniquement des constructeurs drf-spectacular, pour que
chaque ``@extend_schema`` reste sur une ligne lisible.
"""
from decimal import Decimal
from typing import Any, Dict, List

from drf_spectacular.extensions import OpenApiSerializerExtension, OpenApiSerializerFieldExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema_field, inline_serializer
from django.db import models
from rest_framework import serializers
from rest_framework.fields import SkipField, empty

from core.champs_stricts import QUANTITE_MAX, DecimalSouple
from .utils.params import MOTIF_QUANTITE_COMPTEE
from core.serializers import ChampsTexteBooleenStricts

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


class DecimalLie(serializers.DecimalField):
    """Décimal d'un objet lié TOUJOURS servi (api-fuzz « Response violates
    schema », PATCH kits) : DRF saute un champ ``source='lien.attr'`` à défaut
    de valeur dès que le sérialiseur racine est ``partial``, alors que le
    schéma de réponse déclare la clé obligatoire. Même patron que
    ``core.champs_stricts.TexteLie`` : la clé est rendue (``default``/``None``)."""

    def get_attribute(self, instance):
        try:
            return super().get_attribute(instance)
        except SkipField:
            return None if self.default is empty else self.default


class NombreStrict(serializers.FloatField):
    """CI #997 fuzz — nombre JSON réel : un booléen (``false`` lu 0.0) ou une
    chaîne (``"50"``) étaient convertis en silence alors que le schéma publie
    ``number`` ; ils répondent 400."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


class DecimalSoupleStock(DecimalSouple):
    """CI #997 fuzz (2) — décimal stock/achats que des écrans envoient en
    NOMBRE JSON : chaîne OU nombre (publié ``anyOf``, ``DecimalSouple``). Une
    chaîne VIDE n'est pas un décimal : 400 (le schéma ne la publie pas ;
    ``null`` reste « non renseigné » sur un champ nullable). ``borne_min`` /
    ``borne_max`` sont PUBLIÉES (branche nombre, motif chaîne non signé) mais
    contrôlées par le ``validate_<champ>`` du sérialiseur : le message métier
    épinglé par les tests reste le sien (patron ``EntierBornePublie``)."""

    def __init__(self, borne_min=None, borne_max=None, **kwargs):
        super().__init__(**kwargs)
        if borne_min is not None:
            self.min_value = Decimal(str(borne_min))
        if borne_max is not None:
            self.max_value = Decimal(str(borne_max))

    def validate_empty_values(self, data):
        if isinstance(data, str) and not data.strip():
            self.fail('invalid')
        return super().validate_empty_values(data)


#: Bornes MÉTIER publiées par sérialiseur (``validate_<champ>`` les applique
#: déjà) : décimal -> ``DecimalSoupleStock(borne_min, borne_max)``, entier ->
#: ``EntierBornePublie``. Tenu ici : ``serializers.py`` est un fichier-mur.
BORNES_PUBLIEES = {
    'ProduitSerializer': {
        'prix_achat': (0, None), 'prix_vente': (0, None), 'tva': (0, 100),
        'tarif_location_jour': (0, None), 'tarif_location_semaine': (0, None),
        'tarif_location_mois': (0, None), 'quantite_stock': (0, None),
        'seuil_alerte': (0, None)},
    'PaiementFournisseurSerializer': {'montant': ('0.01', None)},
    'AcompteFournisseurSerializer': {'montant': ('0.01', None)},
    'KitComposantSerializer': {'quantite': ('0.01', None), 'taux_perte_pct': (0, '99.99')},
}


class ChampsStrictsSouplesMixin:
    """Mixin de ``ModelSerializer`` (CI #997 fuzz 2) : texte et booléens
    stricts, décimaux ``DecimalSoupleStock`` (chaîne ou nombre, vide refusé) et
    bornes métier de ``BORNES_PUBLIEES`` publiées. À placer AVANT
    ``serializers.ModelSerializer``."""
    serializer_field_mapping = {
        **ChampsTexteBooleenStricts.serializer_field_mapping,
        models.DecimalField: DecimalSoupleStock,
    }

    def build_standard_field(self, field_name, model_field):
        classe, kwargs = super().build_standard_field(field_name, model_field)
        bornes = BORNES_PUBLIEES.get(type(self).__name__, {}).get(field_name)
        if bornes and issubclass(classe, DecimalSoupleStock):
            kwargs.update(borne_min=bornes[0], borne_max=bornes[1])
        elif bornes and issubclass(classe, serializers.IntegerField):
            classe = EntierBornePublie
            kwargs.update(borne_validee='min', min_value=bornes[0])
        return classe, kwargs


class ChampsStrictsProduitMixin(ChampsStrictsSouplesMixin):
    """Fiche produit (CI #997 fuzz) : texte, booléens et décimaux stricts
    (``ChampsStrictsSouplesMixin`` — les écrans envoient des nombres JSON) +
    flottants stricts (``NombreStrict``)."""
    serializer_field_mapping = {
        **ChampsStrictsSouplesMixin.serializer_field_mapping,
        models.FloatField: NombreStrict,
    }


PID = OpenApiParameter(
    name='id', type=INT, location=OpenApiParameter.PATH, description='Identifiant')
PTOKEN = OpenApiParameter(
    name='token_id', type=INT, location=OpenApiParameter.PATH,
    description='Identifiant du jeton')


def corps(_nom, /, **champs):
    """Corps de requête / réponse inline. ``champs`` : ``nom=serializers.X``."""
    return inline_serializer(name=_nom, fields=champs)


@functools.lru_cache(maxsize=None)
def detail_reponse(nom='DetailReponse'):
    # Une seule CLASSE par nom : chaque appel créait un inline_serializer neuf
    # (« identical names and different identities » — backend-openapi, PR #1000).
    return corps(nom, detail=serializers.CharField())


@extend_schema_field({'anyOf': [
    {'type': 'integer', 'minimum': 0, 'maximum': QUANTITE_MAX},
    {'type': 'string', 'pattern': '^(?:' + MOTIF_QUANTITE_COMPTEE + ')$'}]})
class QuantiteComptee(serializers.JSONField):
    """Quantité comptée d'un inventaire : entier 0..``QUANTITE_MAX`` OU chaîne de
    chiffres (l'écran envoie ``Number(saisie)``, des clients le texte). Champ de
    DOCUMENTATION de corps : le contrôle est ``services._quantite_comptee_entiere``."""


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


class _DecimalSoupleStockBorne(OpenApiSerializerFieldExtension):
    """CI #997 fuzz (2) — la borne basse métier d'un ``DecimalSoupleStock`` est
    publiée AUSSI sur la branche chaîne : ``>= 0`` -> motif non signé, ``> 0``
    -> motif strictement positif (la branche nombre la porte déjà en
    ``minimum``). Sinon ``"-5"`` passait pour conforme et répondait 400."""
    target_class = 'apps.stock.openapi_helpers.DecimalSoupleStock'
    priority = 1

    def map_serializer_field(self, auto_schema, direction):
        from core.champs_stricts import _DecimalChaineNonVide
        from .schema_contraintes import _motif_decimal_positif
        champ = self.target
        schema = _DecimalChaineNonVide(champ).map_serializer_field(auto_schema, direction)
        borne = champ.min_value
        if direction != 'request' or borne is None or borne < 0:
            return schema
        for branche in schema.get('anyOf', ()):
            motif = branche.get('pattern')
            if motif and motif.startswith('^-?'):
                branche['pattern'] = (_motif_decimal_positif(motif) if borne > 0
                                      else '^' + motif[3:])
        return schema


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


#: ENF11 — date de requête facultative lue par ``date_ou_400`` / ``_date_param`` :
#: une valeur VIDE (``?fin=``) vaut « non renseignée ». Le schéma publie donc
#: « date OU chaîne vide », ce que le serveur accepte.
DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}


def choix_ou_vide(choix):
    """Filtre à valeurs fermées lu par ``utils.params.statut_requete_ou_400`` :
    une des valeurs, ou la chaîne vide (= filtre non posé)."""
    return {'oneOf': [
        {'type': 'string', 'enum': list(choix)}, {'type': 'string', 'enum': ['']}]}


#: CI #997 fuzz — filtre d'identifiant lu par ``utils.params.id_requete_ou_400`` :
#: un id 1..2147483647, ou la chaîne vide (= filtre non posé).
ID_OU_VIDE = {'oneOf': [
    {'type': 'integer', 'minimum': 1, 'maximum': 2147483647}, {'type': 'string', 'enum': ['']}]}
