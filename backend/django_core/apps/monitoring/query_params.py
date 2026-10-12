"""ASAV67 — lecture VALIDÉE des paramètres de requête du monitoring.

Une saisie invalide (``months=abc``, ``since=pas-une-date``, ``client=abc``…)
doit répondre 400 en nommant le paramètre — jamais 500. UN seul helper pour
toutes les actions (entier borné, date ISO, identifiant, décimal) ; chaque
fonction lève une ``ValidationError`` DRF ``{paramètre: message}``.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError


# Formes EXACTES des schémas publiés (``integer`` / ``format: date`` /
# ``number``). ``int()``, ``date.fromisoformat()`` et ``Decimal()`` lisent bien
# plus (« 5_0 », « +5 », « 20250101 », « 1e1 », blancs de bord, chiffres non
# latins) : ces valeurs étaient acceptées alors que le schéma les refuse.
_ENTIER = re.compile(r'^-?[0-9]+\Z')
_DATE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}\Z')
_NOMBRE = re.compile(r'^-?[0-9]+(\.[0-9]+)?\Z')


def _brut(request, nom):
    return request.query_params.get(nom)


def _entier(brut):
    if not _ENTIER.match(brut):
        raise ValueError(brut)
    return int(brut)


def entier_borne(request, nom, defaut=None, *, mini=1, maxi=None):
    """Entier du paramètre ``nom`` (``defaut`` si absent). Valeur vide ou non
    numérique → 400 ; inférieure à ``mini`` → 400 ; supérieure à ``maxi`` →
    ramenée à ``maxi`` (comportement historique des fenêtres)."""
    brut = _brut(request, nom)
    if brut is None:
        return defaut
    try:
        valeur = _entier(str(brut))
    except (TypeError, ValueError):
        raise ValidationError({nom: 'Entier attendu.'})
    if mini is not None and valeur < mini:
        raise ValidationError({nom: f'Valeur minimale : {mini}.'})
    if maxi is not None and valeur > maxi:
        valeur = maxi
    return valeur


def date_iso(request, nom):
    """Date ISO (AAAA-MM-JJ) du paramètre ``nom``, ``None`` si absent ou vide
    (borne non posée). Date invalide → 400."""
    brut = _brut(request, nom)
    if brut is None or brut == '':
        return None
    try:
        if not _DATE.match(brut):
            raise ValueError(brut)
        return date.fromisoformat(brut)
    except ValueError:
        raise ValidationError({nom: 'Date attendue au format AAAA-MM-JJ.'})


def identifiant(request, nom):
    """Identifiant (entier > 0) du paramètre ``nom``, ``None`` si absent ou
    vide. Non numérique → 400."""
    brut = _brut(request, nom)
    if brut is None or brut == '':
        return None
    try:
        valeur = _entier(brut)
    except (TypeError, ValueError):
        raise ValidationError({nom: 'Identifiant numérique attendu.'})
    if valeur <= 0:
        raise ValidationError({nom: 'Identifiant numérique attendu.'})
    return valeur


def decimal_param(request, nom):
    """Décimal du paramètre ``nom``, ``None`` si absent ou vide. Invalide → 400."""
    brut = _brut(request, nom)
    if brut is None or brut == '':
        return None
    try:
        if not _NOMBRE.match(brut):
            raise ValueError(brut)
        return Decimal(brut)
    except (InvalidOperation, ValueError):
        raise ValidationError({nom: 'Nombre attendu.'})
