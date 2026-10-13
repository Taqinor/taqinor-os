"""Paramètres de requête STRICTS (ENF11) : une valeur illisible ou hors plage
répond 400 nommant le paramètre (jamais ignorée en silence, jamais 500 par
dépassement de date/durée)."""
import re


_ENTIER = re.compile(r'-?[0-9]+')
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
_DECIMAL = re.compile(r'-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?')


def entier_ou_400(valeur, nom, defaut=None, mini=None, maxi=None):
    """Entier de requête STRICT : absent/vide → ``defaut`` ; illisible → 400
    nommant le paramètre ; hors plage → 400 (jamais d'entrée ignorée)."""
    from rest_framework.exceptions import ValidationError
    if valeur is None or str(valeur).strip() == '':
        return defaut
    # Forme exacte du schéma : ni espace, ni « + », ni « 1_0 », ni chiffre non ASCII.
    if not _ENTIER.fullmatch(str(valeur)):
        raise ValidationError({nom: ['Entier attendu.']})
    n = int(valeur)
    if (mini is not None and n < mini) or (maxi is not None and n > maxi):
        raise ValidationError({nom: ['Valeur hors plage.']})
    return n


def date_ou_400(valeur, nom):
    """Date ISO (AAAA-MM-JJ) STRICTE : absente/vide → ``None`` ; illisible → 400
    nommant le paramètre. Rend la chaîne ISO normalisée (les sélecteurs
    existants acceptent des chaînes)."""
    import datetime
    from rest_framework.exceptions import ValidationError
    if valeur is None or str(valeur).strip() == '':
        return None
    try:
        if not _DATE.fullmatch(str(valeur)):
            raise ValueError(valeur)
        return datetime.date.fromisoformat(str(valeur)).isoformat()
    except ValueError:
        raise ValidationError({nom: ['Date AAAA-MM-JJ attendue.']})


def decimal_ou_400(valeur, nom, defaut=None):
    """Nombre décimal STRICT : absent/vide → ``defaut`` ; illisible → 400."""
    from decimal import Decimal, InvalidOperation
    from rest_framework.exceptions import ValidationError
    if valeur is None or str(valeur).strip() == '':
        return defaut
    try:
        if not _DECIMAL.fullmatch(str(valeur)):
            raise InvalidOperation(valeur)
        n = Decimal(str(valeur))
    except InvalidOperation:
        raise ValidationError({nom: ['Nombre attendu.']})
    if not n.is_finite():
        raise ValidationError({nom: ['Nombre attendu.']})
    return n


def corps_objet(request):
    """Corps de requête OBJET (ERR fuzz stock) : un corps JSON non objet
    (``[null, null]``, ``null``, nombre) levait AttributeError sur ``.get``
    (500) ; il répond 400. Rend ``request.data`` (dict ou QueryDict)."""
    from rest_framework.exceptions import ValidationError
    donnees = request.data
    if not hasattr(donnees, 'get'):
        raise ValidationError(
            {'non_field_errors': ['Le corps doit être un objet JSON.']})
    return donnees
