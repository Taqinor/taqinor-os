"""ENF11 — champs de sérialiseur dont le contrat publié (OpenAPI) et le
comportement réel divergeaient, relevés par le fuzz API (Schemathesis).

* ``BooleenStrict`` — ``BooleanField`` de DRF accepte ``0``/``1``, ``"yes"``,
  ``"on"``… alors que le schéma dit ``boolean`` : une écriture JSON avec
  ``"archived": 0`` répondait 200. Ici seuls ``true``/``false`` passent (et
  leurs formes texte ``"true"``/``"false"`` pour un envoi de formulaire).
* ``DateHeureRfc3339`` — pour une date très ancienne (an 960), le fuseau local
  (Africa/Casablanca) rend un décalage « LMT » à secondes (``-00:30:20``) qui
  n'est pas une date-heure RFC 3339 valide : la réponse violait son propre
  schéma. Un décalage à secondes est ramené en UTC (``Z``).
* ``_ChampBlancAutorise`` — extension drf-spectacular : un ``EmailField`` /
  ``URLField`` qui accepte (et rend) la chaîne vide ``""`` publiait
  ``format: email|uri`` seul, donc ``""`` « violait » le schéma. Le schéma dit
  désormais « adresse valide OU chaîne vide ». Effet de schéma uniquement ;
  il vaut pour tout sérialiseur du projet (le contrat devient exact partout).
"""
import datetime

from django.core.validators import RegexValidator
from django.db.models import BooleanField as ModelBooleanField
from django.db.models import CharField as ModelCharField
from django.db.models import TextField as ModelTextField
from django.db.models import DateTimeField as ModelDateTimeField
from django.db.models import DecimalField as ModelDecimalField
from django.db.models import IntegerField as ModelIntegerField
from django.db.models import PositiveIntegerField as ModelPositiveIntegerField
from django.db.models import PositiveSmallIntegerField as ModelPositiveSmallIntegerField
from django.db.models import SmallIntegerField as ModelSmallIntegerField
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers

from core.champs_stricts import ChaineStricte, DecimalStricte, EntierStrict


class BooleenStrict(serializers.BooleanField):
    """Booléen JSON strict : ``true`` / ``false`` (ou ``"true"`` / ``"false"``)."""

    def to_internal_value(self, data):
        if isinstance(data, bool):
            return data
        if isinstance(data, str) and data.strip().lower() in ('true', 'false'):
            return data.strip().lower() == 'true'
        self.fail('invalid', input=data)


class DateHeureRfc3339(serializers.DateTimeField):
    """``DateTimeField`` dont le décalage horaire est toujours RFC 3339."""

    def enforce_timezone(self, value):
        value = super().enforce_timezone(value)
        decalage = value.utcoffset() if value is not None else None
        if decalage is not None and int(decalage.total_seconds()) % 60:
            return value.astimezone(datetime.timezone.utc)
        return value


class IcePublie(RegexValidator):
    """CI #997 (fuzz « rejected schema-compliant request ») — PUBLIE le motif
    d'un ICE valide (vide ou 15 chiffres) dans le schéma : sans lui, un texte
    de 29 chiffres « conforme » (``maxLength`` 30) recevait 400. Ne valide
    RIEN lui-même : ``ClientSerializer.validate_ice`` normalise la saisie
    humaine (« ICE : 001 234 … ») puis contrôle les 15 chiffres ; le motif
    publié n'en est qu'un sous-ensemble strict."""

    def __init__(self):
        super().__init__(regex=r'^(\d{15})?$', message='ICE invalide.',
                         code='invalid')

    def __call__(self, value):
        return None


#: ``ModelSerializer.serializer_field_mapping`` avec les booléens stricts.
MAPPING_BOOLEEN_STRICT = {
    **serializers.ModelSerializer.serializer_field_mapping,
    ModelBooleanField: BooleenStrict,
}

#: ERR-ENF11-FUZZ-CRM — booléens stricts ET textes stricts (référentiels
#: tags / motifs de perte / canaux) : ``CharField`` de DRF convertissait un
#: nombre en texte (``"couleur": 0`` → ``"0"``, 200) alors que le schéma dit
#: ``string`` ; ``ChaineStricte`` répond 400 tant que la valeur n'est pas une
#: vraie chaîne JSON.
MAPPING_TEXTE_STRICT = {
    **MAPPING_BOOLEEN_STRICT,
    ModelCharField: ChaineStricte,
    ModelTextField: ChaineStricte,
}

#: CI #997 (2e passe) — TOUT type JSON exact : textes, booléens, décimaux
#: transportés en CHAÎNE (``DecimalStricte`` : un nombre JSON → 400, ``""`` =
#: « non renseigné » publié pour un champ nullable) et entiers JSON réels
#: (``"5"`` → 400). Pour les sérialiseurs dont AUCUN écran n'envoie un
#: décimal en nombre : la première passe n'avait rendu stricts que les textes
#: et le fuzz remontait le champ suivant de la même opération.
MAPPING_STRICT_COMPLET = {
    **MAPPING_TEXTE_STRICT,
    ModelDecimalField: DecimalStricte,
    ModelIntegerField: EntierStrict,
    ModelPositiveIntegerField: EntierStrict,
    ModelSmallIntegerField: EntierStrict,
    ModelPositiveSmallIntegerField: EntierStrict,
}

#: Idem, avec les dates-heures RFC 3339. CI #997 (fuzz) — textes ET booléens
#: stricts aussi (``notes: 0`` d'un rendez-vous devenait ``"0"``, 201).
MAPPING_DATE_HEURE_RFC3339 = {
    **MAPPING_TEXTE_STRICT,
    ModelDateTimeField: DateHeureRfc3339,
}


def _schema_blanc_autorise(auto_schema, champ, direction):
    schema = auto_schema._map_serializer_field(
        champ, direction, bypass_extensions=True)
    if not getattr(champ, 'allow_blank', False) or 'format' not in schema:
        return schema
    schema = dict(schema)
    forme = schema.pop('format')
    schema['anyOf'] = [{'format': forme}, {'maxLength': 0}]
    return schema


class _EmailBlancAutorise(OpenApiSerializerFieldExtension):
    target_class = 'rest_framework.fields.EmailField'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        return _schema_blanc_autorise(auto_schema, self.target, direction)


class _UrlBlancAutorise(OpenApiSerializerFieldExtension):
    target_class = 'rest_framework.fields.URLField'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        return _schema_blanc_autorise(auto_schema, self.target, direction)
