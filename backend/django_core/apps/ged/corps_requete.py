"""ERR-ENF11-FUZZ-GED — lecture SÛRE des identifiants, dates et textes d'un corps JSON
(``views.py`` est un fichier-mur : les aides vivent ici, importées par les vues)."""
from rest_framework import serializers as drf_serializers


def _pk_ou_none(valeur):
    """Identifiant entier lu d'un corps JSON, ou ``None`` s'il n'en est pas un
    (bool, liste, objet, « abc », 2.5…). Ne lève jamais."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return valeur
    if isinstance(valeur, float) and valeur.is_integer():
        return int(valeur)
    if isinstance(valeur, str) and valeur.strip().lstrip('-').isdigit():
        return int(valeur.strip())
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


def _txt(valeur, nom):
    """Texte optionnel lu d'un corps JSON, nettoyé : une valeur non chaîne
    (nombre, liste, objet) faisait lever ``AttributeError`` sur ``.strip()``
    (500) -> 400 nommant le champ."""
    if valeur is None:
        return ''
    if not isinstance(valeur, str):
        raise drf_serializers.ValidationError({nom: ['Chaîne attendue.']})
    return valeur.strip()
