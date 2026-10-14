"""ENF11 — champs de sérialiseur qui REFUSENT la coercition silencieuse.

``serializers.CharField`` accepte un entier ou un booléen et le convertit en
chaîne (``0`` → ``"0"``) : l'API acceptait alors une donnée que son schéma
OpenAPI déclare invalide (constat api-fuzz « accepted schema-violating
request »). ``ChaineStricte`` répond 400 tant que la valeur n'est pas déjà une
chaîne ; le comportement d'une requête valide est inchangé.
"""
import re
from datetime import date

from django.db import models
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers
from rest_framework.fields import SkipField, empty


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


_DATE_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}\Z')


def date_ou_400(valeur, nom):
    """Date de requête ``AAAA-MM-JJ`` STRICTE : absent/vide -> ``None`` ;
    toute autre forme (``2026-1-5``, ``abc``, jour inexistant) -> 400 nommant
    le paramètre, comme le schéma ``format: date`` le déclare."""
    if valeur is None or str(valeur).strip() == '':
        return None
    brut = str(valeur).strip()
    if _DATE_ISO.match(brut):
        try:
            return date.fromisoformat(brut)
        except ValueError:
            pass
    raise serializers.ValidationError(
        {nom: ['Date attendue au format AAAA-MM-JJ.']})


def nombre_ou_400(valeur, nom, defaut=None, mini=None):
    """Nombre de requête STRICT (``float``) : absent/vide -> ``defaut`` ;
    illisible, ``nan``/``inf`` ou inférieur à ``mini`` -> 400 nommant le
    paramètre (il retombait en silence sur le défaut)."""
    if valeur is None or str(valeur).strip() == '':
        return defaut
    try:
        n = float(str(valeur).strip())
    except ValueError:
        n = None
    if n is None or n != n or n in (float('inf'), float('-inf')) or (
            mini is not None and n < mini):
        raise serializers.ValidationError({nom: ['Nombre attendu.']})
    return n


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


class _DecimalChaineNonVide(OpenApiSerializerFieldExtension):
    r"""ENF11 (api-fuzz « rejected schema-compliant request ») — le motif que
    drf-spectacular publie pour un décimal-chaîne (``^-?\d{0,N}(?:\.\d{0,M})?$``)
    accepte la chaîne VIDE, que ``DecimalField`` refuse (400). Le schéma exige
    désormais au moins un chiffre ; ``""`` n'est publié que pour une
    ``DecimalStricte`` nullable, qui la lit comme « non renseigné »."""
    target_class = 'rest_framework.fields.DecimalField'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        champ = self.target
        schema = auto_schema._map_serializer_field(
            champ, direction, bypass_extensions=True)
        if 'pattern' not in schema or not champ.max_whole_digits:
            return schema
        schema = dict(schema)
        entiers, decimales = champ.max_whole_digits, champ.decimal_places
        schema['pattern'] = (
            fr'^-?(?:\d{{1,{entiers}}}(?:\.\d{{0,{decimales}}})?'
            fr'|\.\d{{1,{decimales}}})$')
        if isinstance(champ, DecimalStricte) and champ.allow_null:
            motif = schema.pop('pattern')
            schema['anyOf'] = [{'pattern': motif}, {'maxLength': 0}]
        return schema


class TexteLie(serializers.CharField):
    """Texte d'un objet lié TOUJOURS servi (api-fuzz « Response violates
    schema »). DRF SAUTE un champ lu via ``source='lien.attr'`` dont le lien est
    vide dès que le sérialiseur est ``partial`` (PATCH) : la clé disparaissait
    de la réponse alors que le schéma la déclare obligatoire. Ici la clé est
    rendue avec son ``default`` (``None``/``''``) comme sur un GET."""

    def get_attribute(self, instance):
        try:
            return super().get_attribute(instance)
        except SkipField:
            return None if self.default is empty else self.default


#: Heure telle que DRF la REND (``time.isoformat()`` d'une heure naïve) :
#: ``HH:MM:SS`` avec microsecondes éventuelles, jamais de décalage.
MOTIF_HEURE_RENDUE = r'^\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$'


class _HeureRendueSansFuseau(OpenApiSerializerFieldExtension):
    """CI #956 (api-fuzz « Response violates schema », parametres/delete-logo) —
    drf-spectacular publie un ``TimeField`` en ``format: time``, que le
    validateur lit comme une « full-time » RFC 3339 (décalage obligatoire,
    ``09:00:00Z``) ; DRF rend ``"09:00:00"``. Côté RÉPONSE le schéma dit le
    motif réellement rendu ; côté requête rien ne change (``format: time``)."""
    target_class = 'rest_framework.fields.TimeField'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(
            self.target, direction, bypass_extensions=True)
        if direction != 'response' or schema.get('format') != 'time':
            return schema
        schema = dict(schema)
        schema.pop('format')
        schema['pattern'] = MOTIF_HEURE_RENDUE
        return schema


def drapeau_ou_400(valeur, nom):
    """Drapeau de requête déclaré ``enum=['1']`` : absent → ``False`` ;
    ``'1'`` → ``True`` ; toute autre valeur → 400 nommant le paramètre (elle
    était lue en silence comme « non »)."""
    if valeur is None:
        return False
    if valeur == '1':
        return True
    raise serializers.ValidationError(
        {nom: ['Seule la valeur « 1 » est acceptée.']})


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


class ChampsStrictsEntiersMixin:
    """``ChampsStrictsMixin`` + ENTIERS stricts (api-fuzz « accepted
    schema-violating request » sur ``PATCH installations/chantiers/{id}/``) :
    texte, booléen, décimal-chaîne et entier de modèle n'acceptent que leur
    type JSON déclaré (``0`` pour un texte, ``"5"`` pour un entier → 400)."""

    serializer_field_mapping = {
        **ChampsStrictsMixin.serializer_field_mapping,
        models.IntegerField: EntierStrict,
        models.PositiveIntegerField: EntierStrict,
        models.SmallIntegerField: EntierStrict,
        models.PositiveSmallIntegerField: EntierStrict,
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
