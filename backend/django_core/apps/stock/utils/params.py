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


#: Quantité comptée écrite en TEXTE (inventaire) : chiffres seuls, au plus
#: ``QUANTITE_MAX`` (1 000 000) — la MÊME forme est publiée et lue.
MOTIF_QUANTITE_COMPTEE = r'[0-9]{1,6}|1000000'

#: Borne d'une clé primaire entière PostgreSQL.
ID_MAX = 2147483647
#: Plancher d'une colonne entière PostgreSQL (``integer``).
ENTIER_MIN = -ID_MAX - 1


def id_corps(valeur):
    """Identifiant lu dans un corps libre (CI #997 fuzz) : ``int`` (jamais un
    booléen) ou chaîne de chiffres, 1..ID_MAX -> ``int`` ; toute autre forme
    (objet, liste, texte, hors plage) -> ``None``. Évite le ``TypeError`` ORM
    (500) d'un ``filter(id={})``."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, str)):
        return None
    if isinstance(valeur, str) and not re.fullmatch(r'[0-9]{1,10}', valeur):
        return None
    n = int(valeur)
    return n if 1 <= n <= ID_MAX else None


def types_corps_ou_400(donnees, textes=(), entiers=(), ids=(), nuls=None, longueurs=None):
    """Corps libre lu À LA MAIN (sans sérialiseur) : chaque champ PRÉSENT et
    non nul doit avoir son type JSON déclaré — texte, entier (jamais un
    booléen ni un flottant), identifiant entier 1..ID_MAX — sinon 400 nommant les
    champs (``note: {}`` était lu ``''``, ``produit: {}`` faisait un 500).

    ``nuls`` (CI #997 fuzz 2) : quand il est donné, seuls ces champs acceptent
    un ``null`` explicite ; sur tout autre champ listé (non nullable au schéma)
    ``null`` répond 400 au lieu d'être lu « vide ».

    CI #997 fuzz (3) — un entier tient dans la colonne entière qui le reçoit
    (``ENTIER_MIN``..``ID_MAX``, le ``maximum`` publié par le modèle) : au-delà,
    400 avant tout calcul (``quantite: 2147483648`` faisait un 500 au save) ;
    ``longueurs`` ({champ: max}) refuse un texte plus long que le ``maxLength``
    publié (il était tronqué en silence)."""
    from rest_framework.exceptions import ValidationError
    erreurs = {}
    for nom in (*textes, *entiers, *ids):
        valeur = donnees.get(nom)
        if valeur is None:
            if nuls is not None and nom in donnees and nom not in nuls:
                erreurs[nom] = ['Ce champ ne peut être nul.']
            continue
        if nom in textes and not isinstance(valeur, str):
            erreurs[nom] = ['Texte attendu.']
        elif nom in entiers and (isinstance(valeur, bool) or not isinstance(valeur, int)):
            erreurs[nom] = ['Entier attendu.']
        elif nom in entiers and not ENTIER_MIN <= valeur <= ID_MAX:
            erreurs[nom] = [f'Entier hors plage ({ENTIER_MIN} à {ID_MAX}).']
        elif nom in textes and len(valeur) > (longueurs or {}).get(nom, len(valeur)):
            erreurs[nom] = [f'Au plus {longueurs[nom]} caractères.']
        elif nom in ids and (isinstance(valeur, bool) or not isinstance(valeur, int)
                             or not 1 <= valeur <= ID_MAX):
            erreurs[nom] = ['Identifiant entier attendu.']
    if erreurs:
        raise ValidationError(erreurs)


def booleen_formulaire_ou_400(donnees, nom):
    """Booléen d'un corps MULTIPART (CI #997 fuzz 2) : absent -> ``False`` ;
    ``true``/``false`` (toute casse — l'écran envoie ``'true'``, un client
    Python ``'True'``) -> bool ; toute autre valeur (``0``, ``peut-etre``) ->
    400 nommant le champ, au lieu d'être lue « non » en silence."""
    from rest_framework.exceptions import ValidationError
    valeur = donnees.get(nom)
    if valeur is None:
        return False
    if str(valeur).lower() not in ('true', 'false'):
        raise ValidationError({nom: ['Booléen attendu (true/false).']})
    return str(valeur).lower() == 'true'


#: Formes booléennes lues dans une query string (précédent ``kits``).
BOOLEENS_REQUETE = ('1', '0', 'true', 'false', 'True', 'False')


def valeur_unique_ou_400(request, nom):
    """Valeur UNIQUE du paramètre ``nom`` (absent -> ``None``) : un paramètre
    déclaré scalaire mais répété (``?x=1&x=1``) répond 400 (CI #997 fuzz)."""
    from rest_framework.exceptions import ValidationError
    valeurs = request.query_params.getlist(nom)
    if len(valeurs) > 1:
        raise ValidationError({nom: ['Une seule valeur attendue.']})
    return valeurs[0] if valeurs else None


def booleen_requete_ou_400(request, nom):
    """Filtre booléen STRICT : absent -> ``None`` ; true/false (1/0) -> bool ;
    toute autre forme (``null``, vide, répétée) -> 400 nommant le paramètre
    (elle était ignorée en silence)."""
    from rest_framework.exceptions import ValidationError
    valeur = valeur_unique_ou_400(request, nom)
    if valeur is None:
        return None
    if valeur not in BOOLEENS_REQUETE:
        raise ValidationError({nom: ['Booléen attendu (true/false).']})
    return valeur in ('1', 'true', 'True')


def id_requete_ou_400(request, nom):
    """Filtre d'identifiant STRICT : absent/vide -> ``None`` ; entier
    1..ID_MAX -> ``int`` ; sinon 400 (``null`` était ignoré en silence).
    Publié ``openapi_helpers.ID_OU_VIDE``."""
    from rest_framework.exceptions import ValidationError
    valeur = valeur_unique_ou_400(request, nom)
    if valeur in (None, ''):
        return None
    n = id_corps(valeur)
    if n is None:
        raise ValidationError({nom: ['Identifiant entier attendu.']})
    return n


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
