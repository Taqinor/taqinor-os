"""ENF11 — lecture VALIDÉE des paramètres de requête de date du reporting.

Le schéma OpenAPI déclare ces paramètres ``format: date`` ; le serveur doit
donc répondre 400 (français, paramètre nommé) à toute valeur qui n'est pas
une date ``AAAA-MM-JJ`` stricte — au lieu de laisser l'ORM lever (500/400
selon le chemin) ou d'accepter une forme tolérée par ``date.fromisoformat``.
"""
import re
from datetime import date

from rest_framework.exceptions import ValidationError

from core.champs_stricts import entier_ou_400

_ISO_STRICT = re.compile(r'^\d{4}-\d{2}-\d{2}$')

# api-fuzz r12 (CI #956, « accepted schema-violating request ») — ``date_param``
# lit « vide » comme « borne non posée » : le schéma le DIT (date ISO ou chaîne
# vide) au lieu d'annoncer une date seule qu'un ``?to=`` contredit. À poser sur
# CHAQUE paramètre lu par ``date_param`` (même patron que monitoring).
DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}
# ``id_param`` refuse 0, les négatifs et ``abc`` (400 nommant le paramètre, au
# lieu d'un 500 de l'ORM) : le schéma annonce ``minimum: 1``.
IDENTIFIANT = {'type': 'integer', 'minimum': 1}


def id_param(request, nom):
    """Identifiant entier STRICT du paramètre ``nom`` : ``None`` si absent ou
    vide ; illisible ou < 1 → 400 nommant le paramètre."""
    return entier_ou_400(request.query_params.get(nom), nom, mini=1)


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
