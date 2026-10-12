"""ENF11 — lecture VALIDÉE des paramètres de requête entiers du SAV.

Une valeur non numérique ou hors bornes répond 400 en nommant le paramètre —
jamais 500 (``int('abc')``, dépassement ``timedelta``/entier PostgreSQL).
"""
import re
from datetime import date

from rest_framework.exceptions import ValidationError

# Borne haute d'une clé primaire PostgreSQL (integer).
ID_MAX = 2147483647

#: CI #956 (api-fuzz « rejected schema-compliant », sav/equipements/?produit=0) —
#: schéma OpenAPI d'un paramètre d'identifiant lu par ``entier_param`` : les
#: bornes PUBLIÉES sont celles que la vue applique (``0`` n'est pas un id).
ENTIER_ID = {'type': 'integer', 'minimum': 1, 'maximum': ID_MAX}

#: Plafond de ``?limit=`` (classements de fiabilité du parc).
LIMITE_MAX = 1000
LIMITE = {'type': 'integer', 'minimum': 1, 'maximum': LIMITE_MAX}


def entier_param(request, nom, defaut=None, *, mini=1, maxi=ID_MAX):
    """Entier du paramètre ``nom`` (``defaut`` si absent ou vide), borné à
    ``[mini, maxi]`` ; sinon 400."""
    brut = request.query_params.get(nom)
    if brut is None or str(brut).strip() == '':
        return defaut
    try:
        valeur = int(str(brut).strip())
    except ValueError:
        raise ValidationError({nom: 'Entier attendu.'})
    if not mini <= valeur <= maxi:
        raise ValidationError(
            {nom: f'Valeur attendue entre {mini} et {maxi}.'})
    return valeur


#: Date ISO ou chaîne vide : ``date_param`` lit « vide » comme « borne non
#: posée » ; le schéma le DIT au lieu d'annoncer une date seule.
DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}

#: ``?export=xlsx`` (ou vide = JSON) — ``choix_param`` refuse toute autre valeur.
EXPORT_XLSX = {'type': 'string', 'enum': ['xlsx', '']}

_ISO_STRICT = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def date_param(request, nom):
    """Date ``AAAA-MM-JJ`` du paramètre ``nom`` (``None`` si absent ou vide) ;
    toute autre forme → 400 nommant le paramètre, jamais ignorée en silence."""
    brut = (request.query_params.get(nom) or '').strip()
    if not brut:
        return None
    try:
        if not _ISO_STRICT.match(brut):
            raise ValueError(brut)
        return date.fromisoformat(brut)
    except ValueError:
        raise ValidationError(
            {nom: 'Date invalide (format attendu : AAAA-MM-JJ).'})


def choix_param(request, nom, choix, defaut=None):
    """Valeur du paramètre ``nom`` parmi ``choix`` (``defaut`` si absent ou
    vide) ; toute autre valeur → 400 nommant le paramètre."""
    brut = request.query_params.get(nom)
    if brut is None or brut == '':
        return defaut
    if brut not in choix:
        raise ValidationError(
            {nom: f"Valeur attendue parmi : {', '.join(choix)}."})
    return brut


def nombre_param(request, nom, mini, maxi):
    """Nombre décimal fini du paramètre ``nom`` dans ``[mini, maxi]`` (``None``
    si absent ou vide) ; sinon 400 nommant le paramètre."""
    brut = (request.query_params.get(nom) or '').strip()
    if not brut:
        return None
    try:
        valeur = float(brut)
    except ValueError:
        valeur = float('nan')
    if not mini <= valeur <= maxi:
        raise ValidationError(
            {nom: f'Nombre attendu entre {mini} et {maxi}.'})
    return valeur
