"""ENF11 — lecture VALIDÉE des paramètres de requête entiers du SAV.

Une valeur non numérique ou hors bornes répond 400 en nommant le paramètre —
jamais 500 (``int('abc')``, dépassement ``timedelta``/entier PostgreSQL).
"""
from rest_framework.exceptions import ValidationError

# Borne haute d'une clé primaire PostgreSQL (integer).
ID_MAX = 2147483647

#: CI #956 (api-fuzz « rejected schema-compliant », sav/equipements/?produit=0) —
#: schéma OpenAPI d'un paramètre d'identifiant lu par ``entier_param`` : les
#: bornes PUBLIÉES sont celles que la vue applique (``0`` n'est pas un id).
ENTIER_ID = {'type': 'integer', 'minimum': 1, 'maximum': ID_MAX}


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
