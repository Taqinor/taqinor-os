"""ASAV67 — lecture VALIDÉE des paramètres de requête du monitoring.

Une saisie invalide (``months=abc``, ``since=pas-une-date``, ``client=abc``…)
doit répondre 400 en nommant le paramètre — jamais 500. UN seul helper pour
toutes les actions (entier borné, date ISO, identifiant, décimal) ; chaque
fonction lève une ``ValidationError`` DRF ``{paramètre: message}``.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError


def _brut(request, nom):
    return request.query_params.get(nom)


def entier_borne(request, nom, defaut=None, *, mini=1, maxi=None):
    """Entier du paramètre ``nom`` (``defaut`` si absent). Valeur vide ou non
    numérique → 400 ; inférieure à ``mini`` → 400 ; supérieure à ``maxi`` →
    ramenée à ``maxi`` (comportement historique des fenêtres)."""
    brut = _brut(request, nom)
    if brut is None:
        return defaut
    try:
        valeur = int(str(brut).strip())
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
    if brut is None or str(brut).strip() == '':
        return None
    try:
        return date.fromisoformat(str(brut).strip())
    except ValueError:
        raise ValidationError({nom: 'Date attendue au format AAAA-MM-JJ.'})


def identifiant(request, nom):
    """Identifiant (entier > 0) du paramètre ``nom``, ``None`` si absent ou
    vide. Non numérique → 400."""
    brut = _brut(request, nom)
    if brut is None or str(brut).strip() == '':
        return None
    try:
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        raise ValidationError({nom: 'Identifiant numérique attendu.'})
    if valeur <= 0:
        raise ValidationError({nom: 'Identifiant numérique attendu.'})
    return valeur


def decimal_param(request, nom):
    """Décimal du paramètre ``nom``, ``None`` si absent ou vide. Invalide → 400."""
    brut = _brut(request, nom)
    if brut is None or str(brut).strip() == '':
        return None
    try:
        return Decimal(str(brut).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError({nom: 'Nombre attendu.'})
