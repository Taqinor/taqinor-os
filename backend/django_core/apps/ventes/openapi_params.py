"""ENF5 — paramètres de requête (OpenAPI) des vues ventes / facturation.

Module SANS import lourd : utilisable depuis ``views/`` comme depuis les
modules de premier niveau. Chaque paramètre lu par une vue
(``request.query_params`` / ``request.GET``) y est déclaré, pour que le schéma
décrive EXACTEMENT ce que le serveur accepte (décision D1 : un futur filtre
plateforme rejettera tout paramètre non déclaré).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter


def qint(name, required=False, desc=None):
    return OpenApiParameter(
        name, OpenApiTypes.INT, required=required, description=desc)


def qstr(name, enum=None, required=False, desc=None):
    return OpenApiParameter(
        name, OpenApiTypes.STR, required=required, enum=enum,
        description=desc)


ENTITE = qint('entite', desc="Filtre optionnel par entité juridique.")
#: ENF11 — ``?month=YYYY-MM`` (mois 01-12, année > 0) et ``?quarter=YYYY-Qn``
#: (n de 1 à 4 ; le serveur accepte aussi ``q`` minuscule) : le schéma dit
#: exactement ce que ``exports.period_bounds`` sait lire (sinon 400 « Période
#: invalide »).
MOIS = r'^(?!0000)\d{4}-(0[1-9]|1[0-2])$'
TRIMESTRE = r'^(?!0000)\d{4}-[Qq][1-4]$'
#: ENF11 (api-fuzz « accepted schema-violating », ``?start=``) — les vues
#: lisent une valeur VIDE comme « non renseignée » (``if start and end``) :
#: le schéma publie « date OU chaîne vide », ce que le serveur accepte
#: (même forme que ``crm.schema_docs.DATE_OU_VIDE``).
DATE_OU_VIDE = {'oneOf': [
    {'type': 'string', 'format': 'date'}, {'type': 'string', 'enum': ['']}]}
#: Mois / trimestre : le motif, ou vide (« non renseigné »).
MOIS_OU_VIDE = r'^(?:(?!0000)\d{4}-(0[1-9]|1[0-2]))?$'
TRIMESTRE_OU_VIDE = r'^(?:(?!0000)\d{4}-[Qq][1-4])?$'


def qdate_ou_vide(name, desc=None):
    return OpenApiParameter(name, DATE_OU_VIDE, OpenApiParameter.QUERY,
                            required=False, description=desc)


PERIODE = [
    OpenApiParameter('month', OpenApiTypes.STR, required=False,
                     description='YYYY-MM', pattern=MOIS_OU_VIDE),
    OpenApiParameter('quarter', OpenApiTypes.STR, required=False,
                     description='YYYY-Qn (n de 1 à 4)',
                     pattern=TRIMESTRE_OU_VIDE),
    qdate_ou_vide('start', 'Date de début (ISO), avec `end`.'),
    qdate_ou_vide('end', 'Date de fin incluse (ISO), avec `start`.'),
]


def entier_requete(request, nom):
    """CI #997 (2) — paramètre ``integer`` publié : absent → ``None`` ;
    répété, vide ou non entier (``?client=null``) → 400 nommant le
    paramètre (il était ignoré en silence, ou levait une 500 au filtre)."""
    from core.pagination import valider_parametre_entier
    brut = valider_parametre_entier(request, nom)
    return None if brut is None else int(brut)


def choix_requete(request, nom, choix):
    """CI #997 (2) — paramètre à ``enum`` publiée : absent → ``None`` ;
    répété ou hors liste (``?concevable=AAA``) → 400 nommant le paramètre."""
    from core.parametres_requete import choix_ou_400
    from rest_framework.exceptions import ValidationError
    if len(request.query_params.getlist(nom)) > 1:
        raise ValidationError(
            {nom: [f"Le paramètre « {nom} » ne doit figurer qu'une fois."]})
    return choix_ou_400(request, nom, choix)
