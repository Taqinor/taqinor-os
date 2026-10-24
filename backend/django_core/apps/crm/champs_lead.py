"""ERR-ENF11-FUZZ-CRM — champs de ``LeadSerializer`` dont le schéma de REQUÊTE
dit EXACTEMENT ce que le serveur accepte.

Constat api-fuzz « rejected schema-compliant request » sur ``POST/PUT/PATCH
crm/leads`` : des listes de mois / jours, un relevé de consommation, une tranche
de facture et un lien Maps étaient publiés sans type (``{}``) ou avec un
``format: uri`` plus large que le validateur — le fuzz envoyait une valeur
« conforme » et recevait 400. Ici le schéma publié EST le prédicat appliqué :
la valeur est validée contre lui (``jsonschema``) AVANT les validateurs du
modèle, qui gardent leurs messages nommés et les règles que le schéma ne dit pas
(mois distincts d'un relevé…).
"""
import re

from django.core import validators as _validateurs
from django.core.exceptions import ValidationError as _ErreurDjango
from drf_spectacular.drainage import set_override
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers

from core.champs_stricts import (
    MOTIF_URL_HTTP_SOUPLE, ChaineStricte, UrlHttpSouple,
)
from core.conflit_etat import ConflitEtat

#: Plafond publié d'un relevé (kWh, kVA…) : au-delà, ``quantize`` à 2 décimales
#: lève ``InvalidOperation`` (28 chiffres significatifs) — c'était un 500.
RELEVE_MAX = 1_000_000_000
#: Nombre décimal en chaîne tel que le formulaire l'envoie (``<input
#: type=number>``) et que le serveur le sert (``"250.00"``).
MOTIF_NOMBRE = r'^(?:[0-9]{1,9}(?:\.[0-9]*)?|\.[0-9]+)$'
#: cos φ en chaîne, dans ]0 ; 1] à deux décimales (le relevé les arrondit).
MOTIF_COS_PHI_RELEVE = r'^(?:1(?:\.0{0,2})?|0?\.(?:[1-9][0-9]?|0[1-9]))$'
#: cos φ de la colonne ``Lead.cos_phi`` (``DecimalField(4, 3)``), dans ]0 ; 1].
MOTIF_COS_PHI = (r'^(?:1(?:\.0{0,3})?|0?\.(?:[1-9][0-9]{0,2}|0[1-9][0-9]?'
                 r'|00[1-9]))$')
MOTIF_MOIS = r'^[0-9]{4}-(?:0[1-9]|1[0-2])$'
MAPS_MAX = 500


def _nullable(schema):
    """``nullable`` posé sur chaque branche (OpenAPI 3.0)."""
    if 'anyOf' in schema:
        return {'anyOf': [dict(b, nullable=True) for b in schema['anyOf']]}
    return dict(schema, nullable=True)


def nombre_ou_texte(minimum=0, maximum=RELEVE_MAX, exclusif=False, motif=None):
    schema = {'type': 'number', 'minimum': minimum, 'maximum': maximum}
    if exclusif:
        schema['exclusiveMinimum'] = True
    return {'anyOf': [schema, {'type': 'string', 'pattern': motif or MOTIF_NOMBRE}]}


def _draft4(schema):
    """Forme OpenAPI 3.0 -> JSON Schema draft 4 (``nullable`` -> type liste)."""
    if isinstance(schema, list):
        return [_draft4(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    sortie = {cle: _draft4(v) for cle, v in schema.items() if cle != 'nullable'}
    if schema.get('nullable') and 'type' in schema:
        sortie['type'] = [schema['type'], 'null']
    return sortie


def entiers_distincts(maximum):
    return {'type': 'array', 'uniqueItems': True,
            'items': {'type': 'integer', 'minimum': 1, 'maximum': maximum}}


_LIGNE_RELEVE = {
    'type': 'object', 'additionalProperties': False,
    'required': ['mois', 'kwh'],
    'properties': {
        'mois': {'type': 'string', 'pattern': MOTIF_MOIS},
        'kwh': nombre_ou_texte(),
        'kwh_pointe': _nullable(nombre_ou_texte()),
        'kwh_pleines': _nullable(nombre_ou_texte()),
        'kwh_creuses': _nullable(nombre_ou_texte()),
        'puissance_atteinte_kva': _nullable(nombre_ou_texte()),
        'cos_phi': _nullable(nombre_ou_texte(
            0.01, 1, motif=MOTIF_COS_PHI_RELEVE)),
    },
}
SCHEMA_RELEVE = {
    'type': 'object', 'additionalProperties': False, 'required': ['mois'],
    'properties': {
        'mois': {'type': 'array', 'maxItems': 12, 'uniqueItems': True,
                 'items': _LIGNE_RELEVE},
        'source': {'type': 'string',
                   'enum': ['declare', 'lu_sur_facture', 'ocr_confirme']},
    },
}
SCHEMA_TRANCHE = {
    'type': 'object', 'additionalProperties': False, 'required': ['min_mad'],
    'properties': {
        'min_mad': nombre_ou_texte(),
        'max_mad': _nullable(nombre_ou_texte()),
        'libelle': {'type': 'string'},
        'source': {'type': 'string', 'enum': ['meta', 'site_web', 'declare']},
    },
}


class JsonLead(serializers.JSONField):
    """``JSONField`` dont le schéma publié (``schema``) est LE prédicat de
    validation. ``null`` reste décidé par ``allow_null`` (colonne nullable)."""

    schema = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        set_override(self, 'field', self.schema)
        self._conforme = None

    def to_internal_value(self, data):
        valeur = super().to_internal_value(data)
        if self._conforme is None:
            import jsonschema
            self._conforme = jsonschema.Draft4Validator(_draft4(self.schema))
        if next(self._conforme.iter_errors(valeur), None) is not None:
            for validateur in self.validators:
                try:
                    validateur(valeur)
                except _ErreurDjango as erreur:
                    raise serializers.ValidationError(erreur.messages)
            raise serializers.ValidationError(
                f'« {self.label or "Ce champ"} » : valeur non conforme.')
        return valeur


class ListeMois(JsonLead):
    schema = entiers_distincts(12)


class ListeJours(JsonLead):
    schema = entiers_distincts(7)


class ReleveConso(JsonLead):
    schema = SCHEMA_RELEVE

    def to_internal_value(self, data):
        valeur = super().to_internal_value(data)
        mois = [ligne['mois'] for ligne in valeur['mois']]
        if len(set(mois)) != len(mois):
            # Règle ENTRE deux éléments : ``uniqueItems`` compare des lignes
            # entières, pas leur mois -> 409, comme la tranche ci-dessous.
            raise ConflitEtat({'releve_conso': [
                '« Relevé de consommation » : un même mois ne peut figurer '
                "qu'une fois."]})
        return valeur


class TrancheDeclaree(JsonLead):
    schema = SCHEMA_TRANCHE

    def to_internal_value(self, data):
        valeur = super().to_internal_value(data)
        from decimal import Decimal
        haut, bas = valeur.get('max_mad'), valeur['min_mad']
        if haut is not None and Decimal(str(haut)) < Decimal(str(bas)):
            # Règle ENTRE deux nombres du corps : aucun schéma ne la dit -> 409.
            raise ConflitEtat({'facture_tranche_declaree': [
                '« Tranche de facture déclarée » : le maximum est inférieur '
                'au minimum.']})
        return valeur


class PeriodeFacture(ChaineStricte):
    """CAD158 — « La facture couvre » : vide, ``mensuelle`` ou
    ``bimestrielle`` (``Lead.PERIODICITES_FACTURE``). Le schéma publie ce
    vocabulaire en ``enum`` (api-fuzz-full 24/10 : un texte libre « conforme »
    recevait 400) ; le refus nommé de ``LeadSerializer.validate`` reste pour
    tout appelant qui n'a pas lu le schéma."""

    def __init__(self, **kwargs):
        from .models import Lead

        super().__init__(**kwargs)
        set_override(self, 'field', {
            'type': 'string', 'enum': ['', *Lead.PERIODICITES_FACTURE]})


class UrlMaps:
    """Prédicat du lien Maps : ``MOTIF_URL_HTTP_SOUPLE`` (celui de
    ``core.champs_stricts.UrlHttpSouple``) et au plus ``MAPS_MAX`` signes
    (``max_length`` du modèle) — le même texte côté schéma et côté serveur."""

    code = 'invalid'
    message = 'Saisissez une URL valide.'
    _motif = re.compile(MOTIF_URL_HTTP_SOUPLE)

    def __call__(self, value):
        if (not isinstance(value, str) or len(value) > MAPS_MAX
                or not self._motif.fullmatch(value)):
            raise _ErreurDjango(self.message, code=self.code)

    def __eq__(self, autre):
        return isinstance(autre, (UrlMaps, UrlHttpSouple))

    def __hash__(self):
        return hash(UrlMaps)


class LienMaps(ChaineStricte):
    """Lien Google Maps du lead : http(s) puis des signes ni blancs ni de
    contrôle, vide permis. Remplace ``format: uri`` + ``URLValidator`` (hôte
    de plus de 253 signes publié conforme puis refusé)."""

    def __init__(self, **kwargs):
        kwargs['validators'] = [
            v for v in kwargs.get('validators', ())
            if not isinstance(v, _validateurs.URLValidator)] + [UrlMaps()]
        kwargs['trim_whitespace'] = False
        super().__init__(**kwargs)


class _LienMaps(OpenApiSerializerFieldExtension):
    target_class = 'apps.crm.champs_lead.LienMaps'
    priority = 1  # avant la règle générique des ChaineStricte (pattern sans nul)

    def map_serializer_field(self, auto_schema, direction):
        if direction == 'request':
            return {'type': 'string', 'maxLength': MAPS_MAX,
                    'pattern': MOTIF_URL_HTTP_SOUPLE}
        return {'type': 'string', 'maxLength': MAPS_MAX}


def schema_cos_phi(nullable):
    """Schéma publié de ``Lead.cos_phi`` : ]0 ; 1] (chaîne OU nombre)."""
    # Minimum 0,0005 : le champ arrondit à 3 décimales (demi-supérieur), donc
    # tout nombre publié donne au moins 0,001 — jamais 0, que le modèle refuse.
    schema = nombre_ou_texte(0.0005, 1, motif=MOTIF_COS_PHI)
    schema['anyOf'][1]['format'] = 'decimal'
    return _nullable(schema) if nullable else schema
