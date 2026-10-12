"""ENF11 — lecture VALIDÉE des paramètres de requête de date du reporting.

Le schéma OpenAPI déclare ces paramètres ``format: date`` ; le serveur doit
donc répondre 400 (français, paramètre nommé) à toute valeur qui n'est pas
une date ``AAAA-MM-JJ`` stricte — au lieu de laisser l'ORM lever (500/400
selon le chemin) ou d'accepter une forme tolérée par ``date.fromisoformat``.
"""
import re
from datetime import date

from rest_framework.exceptions import ValidationError

_ISO_STRICT = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def date_param(request, nom):
    """Chaîne ISO (inchangée) du paramètre ``nom``, ``None`` si absent ou
    vide. Valeur non conforme ``AAAA-MM-JJ`` → 400."""
    brut = request.query_params.get(nom)
    if brut is None or str(brut).strip() == '':
        return None
    brut = str(brut).strip()
    try:
        if not _ISO_STRICT.match(brut):
            raise ValueError(brut)
        date.fromisoformat(brut)
    except ValueError:
        raise ValidationError(
            {nom: 'Date attendue au format AAAA-MM-JJ.'})
    return brut
