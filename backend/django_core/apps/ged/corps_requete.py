"""ERR-ENF11-FUZZ-GED — lecture SÛRE des identifiants, dates et textes d'un corps JSON
(``views.py`` est un fichier-mur : les aides vivent ici, importées par les vues)."""
from rest_framework import serializers as drf_serializers


def _pk(valeur):
    """ERR-ENF11-FUZZ-GED — identifiant lu d'un CORPS JSON, rendu sûr pour
    ``.filter(pk=…)`` : ``"abc"``, une liste, un objet ou un booléen levaient
    ``ValueError``/``TypeError`` (500) ; ils deviennent ``None`` (aucune ligne ->
    les appelants répondent déjà « inconnu » 404/400)."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return valeur
    if isinstance(valeur, float) and valeur.is_integer():
        return int(valeur)
    if isinstance(valeur, str) and valeur.strip().lstrip('-').isdigit():
        return int(valeur.strip())
    return None


def _pks(valeurs):
    """Liste d'identifiants sûrs (``pk__in``) : non-liste -> [] ; éléments
    invalides ignorés."""
    if not isinstance(valeurs, (list, tuple)):
        return []
    return [p for p in (_pk(v) for v in valeurs) if p is not None]


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
