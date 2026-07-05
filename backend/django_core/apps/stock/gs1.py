"""XSTK4 — Parseur GS1-128 / DataMatrix pur Python (stdlib SEULE, aucune
dépendance nouvelle).

Les fabricants (batteries, onduleurs) impriment des codes GS1 composites
concaténant plusieurs Application Identifiers (AI) :
  - ``01`` GTIN (14 chiffres, longueur FIXE) — résout le produit via
    ``Produit.code_barres`` (XSTK3, le GTIN EST le code-barres).
  - ``10`` numéro de lot (alphanumérique, longueur VARIABLE, terminé par le
    séparateur FNC1 ou la fin de la chaîne).
  - ``17`` date de péremption AAMMJJ (6 chiffres, longueur FIXE) → date ISO.
  - ``21`` numéro de série (alphanumérique, longueur VARIABLE, terminé par
    FNC1 ou fin de chaîne).

Le séparateur FNC1 (GS, ``\\x1d``) marque la fin d'un champ à longueur
variable quand un autre AI suit. Un scanner peut aussi émettre le
placeholder textuel ``<GS>`` ou ``{GS}`` (clavier-wedge sans caractère de
contrôle) — les deux formes sont acceptées.

AUCUN appel externe, AUCUNE dépendance tierce (regex + slicing stdlib)."""
import re
from datetime import date

FNC1 = '\x1d'
_FNC1_PLACEHOLDERS = ('<GS>', '{GS}', '[GS]')

# AI → (longueur fixe ou None si variable, nom du champ, transformateur)
_FIXED_LENGTH_AIS = {
    '01': 14,   # GTIN
    '17': 6,    # date de péremption AAMMJJ
}
_VARIABLE_LENGTH_AIS = {'10', '21'}  # lot, série — jusqu'au FNC1/fin

_KNOWN_AIS = set(_FIXED_LENGTH_AIS) | _VARIABLE_LENGTH_AIS


def _normalize_fnc1(raw):
    for placeholder in _FNC1_PLACEHOLDERS:
        raw = raw.replace(placeholder, FNC1)
    return raw


def _parse_gs1_date(value):
    """AAMMJJ GS1 → date ISO. Règle standard GS1 : AA >= 51 → 19AA (rare en
    pratique ici), sinon 20AA. Renvoie None si invalide (jamais une date
    inventée)."""
    if not value or len(value) != 6 or not value.isdigit():
        return None
    yy, mm, dd = int(value[0:2]), int(value[2:4]), int(value[4:6])
    yyyy = 1900 + yy if yy >= 51 else 2000 + yy
    # JJ='00' = dernier jour du mois (règle GS1) — non géré ici : trop rare
    # pour ce parc (batteries/onduleurs indiquent un jour explicite). On
    # refuse proprement plutôt que d'inventer une date.
    if dd == 0:
        return None
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def parse_gs1(raw_code):
    """Décompose un code GS1-128/DataMatrix en champs structurés. Renvoie
    ``{'gtin': str|None, 'lot': str|None, 'date_peremption': date|None,
    'serie': str|None}``. Les AI inconnus/non supportés sont ignorés
    (dégradation propre — jamais une exception sur un composite partiel).
    Une chaîne vide ou sans AI reconnu renvoie tous les champs à None."""
    result = {'gtin': None, 'lot': None, 'date_peremption': None,
              'serie': None}
    if not raw_code:
        return result

    code = _normalize_fnc1(raw_code)
    i = 0
    n = len(code)
    while i < n:
        ai = code[i:i + 2]
        if ai not in _KNOWN_AIS:
            # AI non reconnu : on ne peut pas savoir sa longueur → on
            # s'arrête là plutôt que de mal découper le reste (dégradation
            # propre, jamais une valeur inventée).
            break
        i += 2
        if ai in _FIXED_LENGTH_AIS:
            length = _FIXED_LENGTH_AIS[ai]
            value = code[i:i + length]
            i += length
        else:
            # Longueur variable : jusqu'au FNC1 suivant ou la fin de chaîne.
            gs_pos = code.find(FNC1, i)
            end = gs_pos if gs_pos != -1 else n
            value = code[i:end]
            i = end + 1 if gs_pos != -1 else end

        if ai == '01' and re.fullmatch(r'\d{14}', value or ''):
            result['gtin'] = value
        elif ai == '17':
            result['date_peremption'] = _parse_gs1_date(value)
        elif ai == '10' and value:
            result['lot'] = value
        elif ai == '21' and value:
            result['serie'] = value

    return result
