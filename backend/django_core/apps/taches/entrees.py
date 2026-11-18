"""Bornes des entrées reçues (revue F2 tour 2, constat 12) : une date ou un texte mal formé rend 400, jamais 500.

Feuille de l'app (n'importe que DRF) : les vues, les sérialiseurs et les services lisent ICI les mêmes bornes.

- Une date reçue tient entre `JOUR_MIN` et `JOUR_MAX` (2000-01-01 → 2100-12-31) : au-delà, le calcul d'un jour
  voisin (`+ timedelta`) fait `OverflowError`. Hors plage, le message est celui d'une date illisible.
- `DateBornee` : `DateField` DRF qui applique cette plage (corps de requête) ; `jour_dans_bornes` pour les lectures
  à la main (`?jour=`, services).
- `sans_nul` : un texte libre qui porte `\\x00` est refusé (PostgreSQL ne le stocke pas).
"""
import datetime

from rest_framework import serializers
from rest_framework.settings import api_settings
from rest_framework.utils import humanize_datetime

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
