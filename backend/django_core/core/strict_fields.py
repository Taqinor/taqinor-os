"""ENF11 — champs DRF au typage STRICT (couche de base, ne dépend de rien).

DRF coerce par défaut (12 -> « 12 », "oui" -> True, "5" -> 5) : une requête
que le schéma OpenAPI déclare invalide était acceptée (api-fuzz « API accepted
schema-violating request »). Ces champs refusent tout type JSON autre que
celui publié ; ``TypageStrictMixin`` les pose sur les champs texte / booléen /
entier générés par un ``ModelSerializer``.
"""
from django.db import models
from rest_framework import serializers


class ChaineStricte(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class BooleenStrict(serializers.BooleanField):
    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail('invalid', input=data)
        return data


class EntierStrict(serializers.IntegerField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail('invalid')
        return super().to_internal_value(data)


class TypageStrictMixin:
    """À poser (en premier) sur un ``ModelSerializer`` : champs modèle texte /
    booléen / entier générés en version stricte."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.BooleanField: BooleenStrict,
        models.IntegerField: EntierStrict,
        models.PositiveIntegerField: EntierStrict,
        models.SmallIntegerField: EntierStrict,
        models.PositiveSmallIntegerField: EntierStrict,
    }
