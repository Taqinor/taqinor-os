"""Paramètres de requête STRICTS (ENF11) : une valeur illisible ou hors plage
répond 400 nommant le paramètre (jamais ignorée en silence, jamais 500 par
dépassement de date/durée)."""


def entier_ou_400(valeur, nom, defaut=None, mini=None, maxi=None):
    """Entier de requête STRICT : absent/vide → ``defaut`` ; illisible → 400
    nommant le paramètre ; hors plage → 400 (jamais d'entrée ignorée)."""
    from rest_framework.exceptions import ValidationError
    if valeur is None or str(valeur).strip() == '':
        return defaut
    try:
        n = int(str(valeur).strip())
    except ValueError:
        raise ValidationError({nom: ['Entier attendu.']})
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
        return datetime.date.fromisoformat(str(valeur).strip()).isoformat()
    except ValueError:
        raise ValidationError({nom: ['Date AAAA-MM-JJ attendue.']})


def decimal_ou_400(valeur, nom, defaut=None):
    """Nombre décimal STRICT : absent/vide → ``defaut`` ; illisible → 400."""
    from decimal import Decimal, InvalidOperation
    from rest_framework.exceptions import ValidationError
    if valeur is None or str(valeur).strip() == '':
        return defaut
    try:
        n = Decimal(str(valeur).strip())
    except InvalidOperation:
        raise ValidationError({nom: ['Nombre attendu.']})
    if not n.is_finite():
        raise ValidationError({nom: ['Nombre attendu.']})
    return n
