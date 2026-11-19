"""Bornes des entrées reçues (revue F2 tour 2, constat 12) : une date ou un texte mal formé rend 400, jamais 500.

Feuille de l'app (n'importe que DRF) : les vues, les sérialiseurs et les services lisent ICI les mêmes bornes.

- Une date reçue tient entre `JOUR_MIN` et `JOUR_MAX` (2000-01-01 → 2100-12-31) : au-delà, le calcul d'un jour
  voisin (`+ timedelta`) fait `OverflowError`. Hors plage, le message est celui d'une date illisible.
- `DateBornee` : `DateField` DRF qui applique cette plage (corps de requête) ; `jour_dans_bornes` pour les lectures
  à la main (`?jour=`, services).
- `sans_nul` : un texte libre qui porte `\\x00` est refusé (PostgreSQL ne le stocke pas).
"""
import datetime
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.utils import humanize_datetime

from core.champs_stricts import ChaineStricte

JOUR_MIN = datetime.date(2000, 1, 1)
JOUR_MAX = datetime.date(2100, 12, 31)
MESSAGE_DATE = 'Date attendue (AAAA-MM-JJ).'
MESSAGE_VALEUR = 'Valeur inconnue.'
#: `?exclure=` : au plus 18 chiffres par id (un entier de la base tient dans 19).
LONGUEUR_ID_MAX = 18


def jour_dans_bornes(jour):
    """Vrai si `jour` (une `date`) tient dans la plage acceptée."""
    return JOUR_MIN <= jour <= JOUR_MAX


def sans_nul(valeur):
    """Faux si `valeur` est un texte qui contient le caractère nul."""
    return not (isinstance(valeur, str) and '\x00' in valeur)


class DateBornee(serializers.DateField):
    """`DateField` limité à `[JOUR_MIN, JOUR_MAX]` : hors plage = même erreur qu'une date illisible."""

    def to_internal_value(self, value):
        jour = super().to_internal_value(value)
        if not jour_dans_bornes(jour):
            formats = getattr(self, 'input_formats', None) or api_settings.DATE_INPUT_FORMATS
            self.fail('invalid', format=humanize_datetime.date_formats(formats))
        return jour


# --- Ce que le schéma publie = ce que le serveur accepte (api-fuzz, r2) ----------------------------------
# Le contrôle `positive_data_acceptance` envoie des corps CONFORMES au schéma et exige qu'ils passent : une
# règle que le serveur applique sans la publier (une heure « HH:MM », une plage d'années) fait 400 sur un
# corps « valide ». Chaque règle ci-dessous est donc écrite UNE fois, publiée ET appliquée au même endroit.

#: Années acceptées par `DateBornee` (`JOUR_MIN` → `JOUR_MAX`), publiées en motif à côté de `format: date`.
MOTIF_ANNEE_BORNEE = r'^(?:20[0-9]{2}|2100)-'

#: Une heure murale « HH:MM » (secondes tolérées) : ce que les services lisent (`time.fromisoformat`) sans les
#: formes que personne n'envoie (« 10 », « 1000 », un fuseau). Vérifiée en `fullmatch` (le `$` de Python
#: accepterait un saut de ligne final que le motif publié refuse).
MOTIF_HEURE = r'^(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$'
MESSAGE_HEURE = 'Heure attendue (HH:MM).'
#: Les jours d'une semaine type, lun→dim (`'1111100'`).
MOTIF_SEMAINE = r'^[01]{7}$'


class MotifPublie(RegexValidator):
    """Un motif PUBLIÉ (drf-spectacular lit `regex`) et appliqué en entier (`fullmatch`)."""

    def __init__(self, motif, message):
        super().__init__(regex=motif, message=message, code='invalid')
        self._entier = re.compile(motif)

    def __call__(self, valeur):
        if not isinstance(valeur, str) or not self._entier.fullmatch(valeur):
            raise DjangoValidationError(self.message, code=self.code)


def champ_heure(**options):
    """Une heure « HH:MM » reçue : une vraie chaîne au motif publié, sinon 400 « Heure attendue (HH:MM). »."""
    messages = {'invalid': MESSAGE_HEURE, 'blank': MESSAGE_HEURE, **options.pop('error_messages', {})}
    return ChaineStricte(trim_whitespace=False, validators=[MotifPublie(MOTIF_HEURE, MESSAGE_HEURE)],
                         error_messages=messages, **options)


class HeureStricte(serializers.TimeField):
    """Un `TimeField` qui ne lit que « HH:MM » (secondes tolérées) et le PUBLIE ainsi : `format: time` faisait
    générer des heures RFC 3339 à fuseau (« 00:00:00Z ») que l'app ne reçoit jamais."""

    def to_internal_value(self, valeur):
        if not isinstance(valeur, str) or not re.fullmatch(MOTIF_HEURE, valeur):
            raise serializers.ValidationError(MESSAGE_HEURE, code='invalid')
        return super().to_internal_value(valeur)


class _HeureStrictePubliee(OpenApiSerializerFieldExtension):
    target_class = 'apps.taches.entrees.HeureStricte'
    priority = 1  # avant `core.champs_stricts._HeureRendueSansFuseau` (tout `TimeField`)

    def map_serializer_field(self, auto_schema, direction):
        if direction != 'request':
            return auto_schema._map_serializer_field(self.target, direction, bypass_extensions=True)
        schema = {'type': 'string', 'pattern': MOTIF_HEURE}
        return {**schema, 'nullable': True} if self.target.allow_null else schema


class Choix(serializers.ChoiceField):
    """Une liste fermée de l'app, publiée EN LIGNE (`anyOf: [{enum}]`) : aucun composant `…Enum` partagé avec les
    autres apps (le crochet de nommage des énums de drf-spectacular signalait des collisions « mode »,
    « priorite » — un avertissement de plus rougit `check_openapi_schema`)."""


class ChoixEntier(Choix):
    """Une valeur ENTIÈRE d'une liste fermée (priorité 0-3) : `"2"` ou `true` refusés, comme le schéma le dit."""

    def to_internal_value(self, donnee):
        if isinstance(donnee, bool) or not isinstance(donnee, int):
            self.fail('invalid_choice', input=donnee)
        return super().to_internal_value(donnee)


class _ChoixEnLigne(OpenApiSerializerFieldExtension):
    target_class = 'apps.taches.entrees.Choix'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        champ = self.target
        valeurs = list(champ.choices)
        if getattr(champ, 'allow_blank', False) and '' not in valeurs:
            valeurs.append('')
        entiers = all(isinstance(v, int) and not isinstance(v, bool) for v in valeurs)
        schema = {'type': 'integer' if entiers else 'string'}
        if champ.allow_null:
            schema['nullable'] = True
            valeurs.append(None)
        return {**schema, 'anyOf': [{'enum': valeurs}]}


class _DateBorneePubliee(OpenApiSerializerFieldExtension):
    """`DateBornee` publie sa plage d'années (un `2100-12-31` reste conforme, `1999-…` non)."""

    target_class = 'apps.taches.entrees.DateBornee'
    match_subclasses = True

    def map_serializer_field(self, auto_schema, direction):
        schema = auto_schema._map_serializer_field(self.target, direction, bypass_extensions=True)
        if direction != 'request' or schema.get('format') != 'date':
            return schema
        return {**schema, 'pattern': MOTIF_ANNEE_BORNEE}
