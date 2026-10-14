"""Paramètres de requête STRICTS (ENF11) : une valeur illisible ou hors plage
répond 400 nommant le paramètre (jamais ignorée en silence, jamais 500 par
dépassement de date/durée)."""
import re

from rest_framework.fields import empty


_ENTIER = re.compile(r'-?[0-9]+')
_IDENTIFIANT = re.compile(r'[0-9]{1,9}')
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


def choix_ou_400(valeur, nom, choix):
    """Paramètre de requête à VALEURS FERMÉES (ENF11) : absent/vide -> ``None`` ;
    toute valeur hors ``choix`` -> 400 nommant le paramètre, comme l'énumération
    publiée au schéma (elle retombait en silence sur le défaut)."""
    from rest_framework.exceptions import ValidationError
    if valeur is None or str(valeur) == '':
        return None
    if valeur not in choix:
        raise ValidationError({nom: [
            'Valeur attendue : ' + ', '.join(str(c) for c in choix) + '.']})
    return valeur


#: Forme publiée de ``?ids=`` : identifiants entiers séparés par des virgules.
MOTIF_IDS = r'^[0-9]{1,9}(,[0-9]{1,9})*$'


def ids_requete_ou_400(request, nom='ids'):
    """``?ids=1,2,3`` (ou paramètre répété) STRICT : au moins un identifiant,
    chacun un entier — vide ou illisible -> 400 nommant le paramètre (les
    éléments illisibles étaient ignorés en silence)."""
    from rest_framework.exceptions import ValidationError
    brut = request.query_params.getlist(nom)
    if len(brut) == 1 and ',' in brut[0]:
        brut = brut[0].split(',')
    if not brut or any(not _IDENTIFIANT.fullmatch(x) for x in brut):
        raise ValidationError({nom: [
            'Sélectionnez au moins un produit (identifiants entiers '
            'séparés par des virgules).']})
    return brut


def _unicite_seule(exc):
    """Vrai si ``exc`` (``ValidationError``) ne porte QUE des refus d'unicité."""
    codes = exc.get_codes()
    return (isinstance(codes, dict) and bool(codes) and all(
        isinstance(v, list) and v and all(c == 'unique' for c in v)
        for v in codes.values()))


class UniciteEn409Mixin:
    """Mixin de SÉRIALISEUR : un DOUBLON refusé par les validateurs d'unicité de
    DRF (``unique``) répond 409 ``unique_conflict`` (le corps était conforme,
    c'est l'état des données qui s'y oppose) ; une requête qui porte AUSSI une
    autre erreur reste un 400. Même règle que
    ``crm.params_requete.UniciteEn409Mixin``, posée sur le sérialiseur pour que
    la forme de la ressource reste lisible par ``check_api_shapes``."""

    def run_validation(self, data=empty):
        from rest_framework.exceptions import ValidationError
        from core.unicite import ConflitUnicite
        try:
            return super().run_validation(data)
        except ValidationError as exc:
            if not _unicite_seule(exc):
                raise
            champs = [c for c in exc.detail if c != 'non_field_errors']
            raise ConflitUnicite(
                detail=str(next(iter(exc.detail.values()))[0]),
                champs=champs) from exc
