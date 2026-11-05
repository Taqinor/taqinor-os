"""NTDATA10 — sérialiseur du CRUD des métriques nommées.

La société n'est JAMAIS un champ : elle est posée côté serveur
(``TenantMixin.perform_create``). La validation de la MESURE est celle du
modèle (``MetricDefinition.clean``) — une seule règle, jamais une seconde qui
dériverait : on la rejoue ici sur une instance non enregistrée et on remonte
ses messages FRANÇAIS champ par champ.
"""
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers

from core.champs_stricts import BooleenStrict, ChampsStrictsMixin
from core.parseurs import ObjetJSON
from core.unicite import UniciteEn409Mixin

from .models import AGREGATIONS, MetricDefinition
from .portabilite import CHAMPS_PORTABLES, FORMAT, MAX_METRIQUES_IMPORT

#: Forme d'une clé de métrique (celle des 8 métriques cœur : ``ca_ht``, ``dso``).
_CLE_VALIDE = re.compile(r'^[a-z][a-z0-9_]{0,79}$')
_MESSAGE_CLE = ('La clé ne contient que des lettres minuscules, des chiffres '
                'et « _ » (ex. « marge_brute »), et commence par une lettre.')

#: ENF47 (api-fuzz-full 42017839549, « rejected schema-compliant request ») —
#: la forme de ``mesure`` PUBLIÉE telle que ``MetricDefinition.clean`` la lit
#: (``JSONField`` publiait ``{}`` : ``null`` ou ``{}`` étaient conformes puis
#: 400). Une des quatre formes : adaptateur, formule, ``count``, agrégat sur un
#: champ ; une formule « vide » (valeur fausse) désigne une mesure simple. Les
#: textes lus sont sans caractère nul (``ObjetJSON`` le retire, le schéma
#: publié l'exclut : conforme ⇒ inchangé par ce retrait). OpenAPI 3.0 : ni
#: ``propertyNames`` ni ``const`` ; énumérations sous ``allOf`` (comme
#: ``ChoixDocumente`` : aucun composant ``<Prop>Enum`` créé ni renommé).
_TEXTE_LU = {'type': 'string', 'pattern': '^[^\u0000]+$'}


def _parmi(valeurs):
    return {'allOf': [{'enum': list(valeurs)}]}


_FORMULE_VIDE = _parmi([None, False, '', 0, [], {}])
SCHEMA_MESURE = {'type': 'object', 'anyOf': [
    {'required': ['adapter'], 'properties': {'adapter': _TEXTE_LU}},
    {'required': ['formula', 'aggregates'], 'properties': {
        'formula': _TEXTE_LU,
        'aggregates': {'type': 'array', 'minItems': 1, 'items': {
            'type': 'object', 'required': ['alias', 'fn'],
            'properties': {'alias': _TEXTE_LU,
                           'fn': _parmi(AGREGATIONS)}}}}},
    {'required': ['agg'], 'properties': {
        'agg': _parmi(['count']), 'formula': _FORMULE_VIDE}},
    {'required': ['agg', 'field'], 'properties': {
        'agg': _parmi(a for a in AGREGATIONS if a != 'count'),
        'field': _TEXTE_LU, 'formula': _FORMULE_VIDE}},
]}


class MesureJSON(ObjetJSON):
    """ENF47 — ``mesure`` : un objet (``null`` refusé) de forme
    ``SCHEMA_MESURE``, publié ET appliqué (le JSON brut est jugé, avant le
    retrait du caractère nul) ; refus en 400 nommé, message de ``clean``."""

    def __init__(self, **kwargs):
        from drf_spectacular.drainage import set_override
        super().__init__(**kwargs)
        set_override(self, 'field', SCHEMA_MESURE)

    def to_internal_value(self, data):
        import jsonschema
        if isinstance(data, dict) and not jsonschema.Draft7Validator(
                SCHEMA_MESURE).is_valid(data):
            try:
                MetricDefinition(cle='x', dataset='x', mesure=data).clean()
                message = None
            except DjangoValidationError as exc:
                message = exc.message_dict.get('mesure', [None])[0]
            raise serializers.ValidationError(message or (
                'La mesure doit être {"field": …, "agg": …}, {"agg": "count"}, '
                '{"formula": …, "aggregates": […]} ou {"adapter": …}.'))
        return super().to_internal_value(data)


class MetricDefinitionSerializer(UniciteEn409Mixin, ChampsStrictsMixin,
                                 serializers.ModelSerializer):
    """Une métrique nommée : clé, dataset, mesure, unité, filtres."""

    mesure = MesureJSON()  # ENF47 — forme publiée et appliquée, null refusé

    class Meta:
        model = MetricDefinition
        fields = [
            'id', 'cle', 'libelle', 'description', 'dataset', 'mesure',
            'unite', 'format', 'dimensions_par_defaut', 'filtres', 'actif',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        # ENF11 (nocturne 41958593088, dCl2lo) : la forme de la clé est PUBLIÉE
        # (motif au schéma via RegexValidator) — « 0 » était conforme puis 400.
        # ENF45 d : sans ``mesure`` (défaut ``{}``) ``MetricDefinition.clean``
        # refusait un corps que le schéma disait complet — elle est REQUISE à
        # la création (et au PUT) ; PATCH la garde facultative.
        extra_kwargs = {'cle': {'validators': [
            RegexValidator(_CLE_VALIDE, message=_MESSAGE_CLE)]}}

    def validate_cle(self, value):
        # La clé voyage dans les URL (`metriques/<cle>/valeur/`) et dans les
        # layouts de tableaux de bord : un identifiant simple, jamais une
        # phrase.
        if not _CLE_VALIDE.match(value or ''):
            raise serializers.ValidationError(_MESSAGE_CLE)
        return value

    def validate_mesure(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'La mesure doit être un objet JSON.')
        return value

    def validate_filtres(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Les filtres doivent être un objet JSON.')
        return value

    def validate_dimensions_par_defaut(self, value):
        if value in (None, ''):
            return []
        if (not isinstance(value, list)
                or not all(isinstance(v, str) and v for v in value)):
            raise serializers.ValidationError(
                'Les dimensions par défaut doivent être une liste de noms de '
                'champs.')
        return value

    def validate(self, attrs):
        """Rejoue ``MetricDefinition.clean`` sur l'état FINAL de la ligne."""
        attrs = super().validate(attrs)
        etat = {}
        if self.instance is not None:
            for champ in ('cle', 'dataset', 'mesure'):
                etat[champ] = getattr(self.instance, champ)
        etat.update({k: v for k, v in attrs.items()
                     if k in ('cle', 'dataset', 'mesure')})
        try:
            MetricDefinition(**etat).clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(
                getattr(exc, 'message_dict', None) or {'mesure': exc.messages})
        return attrs


class EntreeMetriqueJSON(serializers.JSONField):
    """ENF48 (api-fuzz-full 42074433075, « rejected schema-compliant ») — une
    entrée d'import : un objet aux SEULES clés portables, clé requise, chaque
    valeur jugée par le champ du CRUD (type, motif, forme de mesure) ; publié
    TEL QUEL (propriétés du corps CRUD, ``additionalProperties: false``) et
    refusé en 400 nommé, même en dry-run. Ce qui dépend de l'ÉTAT (métrique
    existante ou non, champs requis à la création, doublon dans le document)
    reste jugé ligne à ligne par ``portabilite``."""

    def to_internal_value(self, data):
        from core.parseurs import sans_nul
        if not isinstance(data, dict):
            raise serializers.ValidationError('Un objet JSON est attendu.')
        inconnues = sorted(set(data) - set(CHAMPS_PORTABLES))
        if inconnues:
            raise serializers.ValidationError(
                {k: 'Clé non portable (refusée).' for k in inconnues})
        if 'cle' not in data:
            raise serializers.ValidationError(
                {'cle': 'Ce champ est obligatoire.'})
        MetricDefinitionSerializer(partial=True).to_internal_value(data)
        return super().to_internal_value(sans_nul(data))


class _EntreeMetriqueSchema(OpenApiSerializerFieldExtension):
    """Publie l'entrée : les propriétés PORTABLES du corps CRUD, rien d'autre."""
    target_class = 'apps.semantic.serializers.EntreeMetriqueJSON'

    def map_serializer_field(self, auto_schema, direction):
        import copy
        corps = auto_schema.resolve_serializer(
            MetricDefinitionSerializer, 'request').schema or {}
        proprietes = {k: v for k, v in (corps.get('properties') or {}).items()
                      if k in CHAMPS_PORTABLES}
        return {'type': 'object', 'properties': copy.deepcopy(proprietes),
                'required': ['cle'], 'additionalProperties': False}


class ImportMetriquesSerializer(serializers.Serializer):
    """NTDATA48 — corps de ``POST semantic/metriques/import/``.

    ``metriques`` : les entrées du document d'export (chacune revalidée par
    ``MetricDefinitionSerializer`` + la liste blanche de ``portabilite``) ;
    ``commit`` : ``false`` (défaut) = dry-run, ``true`` = appliquer.
    """

    # ENF11 (nocturne 41958593088, VKjai2) : le SEUL format lisible est
    # publié (motif exact, sans composant d'énumération qui renommerait le
    # ``FormatEnum`` voisin) — un texte quelconque était conforme puis 400.
    format = serializers.RegexField(
        r'^(?:%s)?$' % re.escape(FORMAT), required=False, allow_blank=True,
        error_messages={'invalid': (
            'Document étranger : format « %s » attendu.' % FORMAT)})
    version = serializers.IntegerField(required=False, min_value=1)
    metriques = serializers.ListField(
        # ENF47 (api-fuzz-full 42017839549) : une entrée est un OBJET, publié
        # et appliqué (``ObjetJSON``) — une liste ou ``null`` était conforme
        # au schéma ``{}`` puis refusé ligne à ligne (400 en ``commit``). Le
        # CONTENU d'un objet est jugé par ``EntreeMetriqueJSON`` (ENF48), l'ÉTAT
        # ligne à ligne par ``portabilite``.
        child=EntreeMetriqueJSON(), allow_empty=True,
        max_length=MAX_METRIQUES_IMPORT)
    commit = BooleenStrict(required=False, default=False)
