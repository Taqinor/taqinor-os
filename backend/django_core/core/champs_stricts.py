"""ENF11 — champs de sérialiseur qui REFUSENT la coercition silencieuse.

``serializers.CharField`` accepte un entier ou un booléen et le convertit en
chaîne (``0`` → ``"0"``) : l'API acceptait alors une donnée que son schéma
OpenAPI déclare invalide (constat api-fuzz « accepted schema-violating
request »). ``ChaineStricte`` répond 400 tant que la valeur n'est pas déjà une
chaîne ; le comportement d'une requête valide est inchangé.
"""
from django.db import models
from rest_framework import serializers


class ChaineStricte(serializers.CharField):
    """``CharField`` qui n'accepte que de vraies chaînes JSON."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


def entier_ou_400(valeur, nom, defaut=None, mini=None, maxi=None):
    """Entier de requête STRICT : absent/vide -> ``defaut`` ; illisible ou
    inférieur à ``mini`` -> 400 nommant le paramètre ; supérieur à ``maxi`` ->
    plafonné (comportement historique des paramètres ``limit``)."""
    if valeur is None or str(valeur).strip() == '':
        return defaut
    try:
        n = int(str(valeur).strip())
    except ValueError:
        raise serializers.ValidationError({nom: ['Entier attendu.']})
    if mini is not None and n < mini:
        raise serializers.ValidationError({nom: ['Valeur hors plage.']})
    return n if maxi is None else min(n, maxi)


class DecimalStricte(serializers.DecimalField):
    """Décimal transporté en CHAÎNE (comme le schéma le déclare) : un nombre
    ou un booléen JSON est refusé en 400 ; ``""`` vaut « non renseigné » quand
    le champ accepte ``null``."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)

    def validate_empty_values(self, data):
        if data == '' and self.allow_null:
            return (True, None)
        return super().validate_empty_values(data)


class BooleenStrict(serializers.BooleanField):
    """``BooleanField`` qui n'accepte que de vrais booléens JSON (``0``/``1``
    ou ``"true"`` étaient convertis en silence)."""

    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail('invalid', input=data)
        return data


class EntierStrict(serializers.IntegerField):
    """Entier JSON réel : ``"5"``, ``5.0`` et ``true`` sont refusés (400)."""

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, int):
            self.fail('invalid')
        return super().to_internal_value(data)


class ChampsStrictsMixin:
    """Mixin de ``ModelSerializer`` : les champs de modèle texte, booléens et
    décimaux sont générés en version STRICTE (un ``0`` pour un booléen ou un
    nombre JSON pour un décimal-chaîne → 400, comme le schéma le déclare).
    À placer AVANT ``serializers.ModelSerializer`` dans les bases."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.TextField: ChaineStricte,
        models.BooleanField: BooleenStrict,
        models.DecimalField: DecimalStricte,
    }


class ChampsStrictsSansDecimalMixin:
    """Variante de ``ChampsStrictsMixin`` SANS les décimaux (lane GED/records/
    notifications : leurs clients envoient encore des nombres JSON pour
    ``x``/``y``/``largeur``…) — texte et booléens stricts seulement."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.TextField: ChaineStricte,
        models.BooleanField: BooleenStrict,
    }


class TypageStrictMixin:
    """Variante (lane parametres/sav) : champs modèle texte / booléen / ENTIER
    générés en version stricte (``"5"`` pour un entier → 400) ; ``TextField``
    et décimaux inchangés. À poser en premier sur un ``ModelSerializer``."""

    serializer_field_mapping = {
        **serializers.ModelSerializer.serializer_field_mapping,
        models.CharField: ChaineStricte,
        models.BooleanField: BooleenStrict,
        models.IntegerField: EntierStrict,
        models.PositiveIntegerField: EntierStrict,
        models.SmallIntegerField: EntierStrict,
        models.PositiveSmallIntegerField: EntierStrict,
    }
