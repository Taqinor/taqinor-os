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


# ---------------------------------------------------------------------------
# NTWMS6 -- SSCC (Serial Shipping Container Code, AI 00) : 18 chiffres GS1.
#
# Structure : 1 chiffre d'extension + prefixe entreprise + reference serie
# (ensemble 16 chiffres) + 1 cle de controle mod-10 GS1. Calcul en stdlib
# pure -- aucune dependance externe (regle du depot).
# ---------------------------------------------------------------------------

SSCC_LONGUEUR = 18


def cle_controle_gs1(chiffres):
    """Cle de controle GS1 (mod-10) des chiffres FOURNIS (sans la cle).

    Ponderation 3/1 en partant de la DROITE, puis complement a la dizaine
    superieure. Leve ValueError si l'entree n'est pas purement numerique.
    """
    chiffres = str(chiffres or '').strip()
    if not chiffres.isdigit():
        raise ValueError('La cle de controle GS1 exige des chiffres.')
    total = 0
    for rang, caractere in enumerate(reversed(chiffres)):
        poids = 3 if rang % 2 == 0 else 1
        total += int(caractere) * poids
    return (10 - (total % 10)) % 10


def construire_sscc(prefixe_entreprise, reference_serie, extension='0'):
    """SSCC 18 chiffres a partir du prefixe entreprise + reference de serie.

    Le corps (extension + prefixe + reference) est zero-pade a 17 chiffres,
    puis la cle de controle est ajoutee. Leve ValueError si le corps depasse
    17 chiffres ou n'est pas numerique.
    """
    extension = str(extension or '0').strip() or '0'
    prefixe = str(prefixe_entreprise or '').strip()
    reference = str(reference_serie or '').strip()
    if not (extension + prefixe + reference).isdigit():
        raise ValueError('Un SSCC ne contient que des chiffres.')
    if len(extension) != 1:
        raise ValueError("Le chiffre d'extension SSCC fait 1 chiffre.")
    corps = extension + prefixe
    reste = SSCC_LONGUEUR - 1 - len(corps)
    if reste < len(reference) or reste < 0:
        raise ValueError('Prefixe + reference depassent la longueur SSCC.')
    corps = corps + reference.rjust(reste, '0')
    return corps + str(cle_controle_gs1(corps))


def sscc_valide(code):
    """Vrai si `code` est un SSCC bien forme (18 chiffres, cle correcte)."""
    code = str(code or '').strip()
    if len(code) != SSCC_LONGUEUR or not code.isdigit():
        return False
    return str(cle_controle_gs1(code[:-1])) == code[-1]
