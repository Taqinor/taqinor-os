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
PERIODE = [
    qstr('month', desc='YYYY-MM'),
    qstr('quarter', desc='YYYY-Q'),
    qstr('start', desc='Date de début (ISO), avec `end`.'),
    qstr('end', desc='Date de fin incluse (ISO), avec `start`.'),
]
