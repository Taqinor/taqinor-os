"""ERR-ENF11-FUZZ-GED — lecture SÛRE des identifiants, dates et textes d'un corps JSON
(``views.py`` est un fichier-mur : les aides vivent ici, importées par les vues)."""
from rest_framework import serializers as drf_serializers


# Aucune clé primaire GED ne dépasse un entier PostgreSQL 32 bits : au-delà, la
# ligne n'existe pas (et la comparaison SQL, elle, déborderait).
_PK_MAX = 2147483647
ID_INEXISTANT = -1


def _borne_pk(n):
    return n if -_PK_MAX <= n <= _PK_MAX else ID_INEXISTANT


def _pk_ou_none(valeur):
    """Identifiant entier lu d'un corps JSON, ou ``None`` s'il n'en est pas un
    (bool, liste, objet, « abc », 2.5…). Ne lève jamais. Un entier hors de la
    plage 32 bits rend ``ID_INEXISTANT`` (aucune ligne : 404, jamais une 500)."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return _borne_pk(valeur)
    if isinstance(valeur, float) and valeur.is_integer():
        return _borne_pk(int(valeur))
    if isinstance(valeur, str) and valeur.strip().lstrip('-').isdigit():
        return _borne_pk(int(valeur.strip()))
    return None


def _pk(valeur, nom='detail'):
    """ERR-ENF11-FUZZ-GED — identifiant lu d'un CORPS JSON, rendu sûr pour
    ``.filter(pk=…)``.

    Absent (``None``, ``""``, ``"null"``) → ``None`` : l'appelant décide
    (« requis » 400 ou optionnel). MAL FORMÉ (``"abc"``, ``"{}"``, liste,
    objet, booléen, 2.5) → 400 nommant le champ : c'est une entrée invalide,
    pas un objet inconnu — le 404 « inconnu » reste réservé à un entier qui
    ne désigne aucune ligne visible (CI #956, core/tests/test_acal_500_journalise
    `test_fk_accolades_du_corps_400`). Avant : ``ValueError`` (500) ; puis
    ``None`` pour tout, qui confondait « mal formé » et « inconnu » en 404."""
    if valeur is None or (isinstance(valeur, str)
                          and valeur.strip() in ('', 'null')):
        return None
    pk = _pk_ou_none(valeur)
    if pk is None:
        raise drf_serializers.ValidationError(
            {nom: ['Identifiant entier attendu.']})
    return pk


def _pks(valeurs):
    """Liste d'identifiants sûrs (``pk__in``) : non-liste -> [] ; éléments
    invalides ignorés."""
    if not isinstance(valeurs, (list, tuple)):
        return []
    return [p for p in (_pk_ou_none(v) for v in valeurs) if p is not None]


def _date_iso(valeur):
    """Date ``AAAA-MM-JJ`` STRICTE (le schéma déclare ``format: date``) :
    ``parse_date`` acceptait ``2026-1-1`` ; un non-texte est refusé. ``None`` si
    invalide."""
    import re
    from django.utils.dateparse import parse_date
    if not isinstance(valeur, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}', valeur.strip()):
        return None
    try:
        return parse_date(valeur.strip())
    except ValueError:
        return None


def _txt(valeur, nom, max_length=None):
    """Texte optionnel lu d'un corps JSON, nettoyé : une valeur non chaîne
    (nombre, liste, objet) faisait lever ``AttributeError`` sur ``.strip()``
    (500) -> 400 nommant le champ. Le caractère NUL (refusé par PostgreSQL) et
    un texte plus long que la colonne cible (``max_length``) sont aussi un 400
    — c'étaient des 500 (``DataError``)."""
    if valeur is None:
        return ''
    if not isinstance(valeur, str):
        raise drf_serializers.ValidationError({nom: ['Chaîne attendue.']})
    if '\x00' in valeur:
        raise drf_serializers.ValidationError(
            {nom: ['Caractère nul interdit.']})
    valeur = valeur.strip()
    if max_length is not None and len(valeur) > max_length:
        raise drf_serializers.ValidationError(
            {nom: [f'{max_length} caractères au plus.']})
    return valeur


def _id_filtre(params, nom, *, null_ok=False):
    """Filtre de requête « identifiant » (``?folder=12``), STRICT : absent ->
    ``None`` ; ``null`` (si ``null_ok``) -> ``'null'`` ; entier -> ``int`` ;
    tout autre texte, VIDE compris, -> 400 nommant le paramètre (il était
    ignoré en silence). Hors plage 32 bits -> ``ID_INEXISTANT`` (liste vide)."""
    import re
    brut = params.get(nom)
    if brut is None:
        return None
    if null_ok and brut == 'null':
        return 'null'
    if re.fullmatch(r'-?[0-9]{1,30}', brut):
        return _borne_pk(int(brut))
    raise drf_serializers.ValidationError(
        {nom: ['Identifiant entier attendu.']})


def _entier_borne(params, nom, *, defaut, mini, maxi):
    """Paramètre de requête entier dans ``[mini, maxi]`` : absent -> ``defaut`` ;
    illisible, vide ou hors bornes -> 400 nommant le paramètre (il retombait
    sur le défaut ou était plafonné en silence)."""
    import re
    brut = params.get(nom)
    if brut is None:
        return defaut
    if re.fullmatch(r'-?[0-9]{1,30}', brut):
        n = int(brut)
        if mini <= n <= maxi:
            return n
    raise drf_serializers.ValidationError(
        {nom: [f'Entier entre {mini} et {maxi} attendu.']})
