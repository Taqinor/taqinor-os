"""ENF3 — aides de description OpenAPI de l'app installations.

Aucune logique métier : uniquement des fabriques de champs/paramètres pour
que chaque vue décrive EXACTEMENT ce qu'elle lit et renvoie (corps, paramètres
de requête, statuts, binaires).

* ``JsonOnlyMixin`` (décision fondateur D2) : une vue SANS dépôt de fichier
  n'accepte et ne documente que le JSON ; les actions d'upload repassent en
  multipart via ``parser_classes`` sur l'``@action``.
* Les corps/réponses libres sont typés au plus juste : un champ optionnel
  n'est jamais déclaré obligatoire (sinon ACC), un champ réellement exigé par
  le code l'est (sinon REJ).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (  # noqa: F401  (ré-exportés)
    OpenApiParameter, extend_schema, extend_schema_view, inline_serializer,
)
from rest_framework import serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

UPLOAD_PARSERS = [MultiPartParser, FormParser]
JSON_AND_UPLOAD_PARSERS = [JSONParser, MultiPartParser, FormParser]


class JsonOnlyMixin:
    """D2 — JSON seulement (les actions d'upload surchargent ``parser_classes``)."""
    parser_classes = [JSONParser]


# ── champs de corps / de réponse ──────────────────────────────────────────────
def i(required=False, null=False, **kw):
    return serializers.IntegerField(
        required=required, allow_null=null, **kw)


def s(required=False, null=False, **kw):
    return serializers.CharField(
        required=required, allow_null=null, allow_blank=not required, **kw)


def b(required=False, **kw):
    return serializers.BooleanField(required=required, **kw)


def f(required=False, null=False, **kw):
    return serializers.FloatField(required=required, allow_null=null, **kw)


def d(required=False, null=False, **kw):
    return serializers.DateField(required=required, allow_null=null, **kw)


def dt(required=False, null=False, **kw):
    return serializers.DateTimeField(required=required, allow_null=null, **kw)


def dec(required=False, null=False, **kw):
    # Décimal accepté en nombre OU en chaîne par le code (Decimal(str(x))).
    return serializers.CharField(
        required=required, allow_null=null, allow_blank=False, **kw)


def obj(required=False, null=False, **kw):
    return serializers.DictField(required=required, allow_null=null, **kw)


def lst(child=None, required=False, null=False, **kw):
    return serializers.ListField(
        child=child or serializers.DictField(), required=required,
        allow_null=null, **kw)


def ints(required=False, **kw):
    return serializers.ListField(
        child=serializers.IntegerField(), required=required, **kw)


def choice(values, required=False, **kw):
    return serializers.ChoiceField(
        choices=list(values), required=required, **kw)


def body(name, **fields):
    """Sérialiseur de corps/réponse nommé (composant OpenAPI stable)."""
    return inline_serializer(name, fields=fields)


# ── paramètres de requête ─────────────────────────────────────────────────────
def q(name, typ=OpenApiTypes.STR, required=False, enum=None, desc=None,
      **kw):
    extra = {}
    if enum is not None:
        extra['enum'] = list(enum)
    if desc:
        extra['description'] = desc
    return OpenApiParameter(
        name, typ, OpenApiParameter.QUERY, required=required, **extra, **kw)


def qi(name, **kw):
    return q(name, OpenApiTypes.INT, **kw)


def qs(name, **kw):
    return q(name, OpenApiTypes.STR, **kw)


def qd(name, **kw):
    return q(name, OpenApiTypes.DATE, **kw)


def qb(name, **kw):
    return q(name, OpenApiTypes.BOOL, **kw)


def qf(name, **kw):
    return q(name, OpenApiTypes.FLOAT, **kw)


# ── réponses non-JSON ─────────────────────────────────────────────────────────
PDF = {(200, 'application/pdf'): OpenApiTypes.BINARY}
HTML = {(200, 'text/html'): OpenApiTypes.STR}
OBJ = OpenApiTypes.OBJECT
LIST = serializers.ListField(child=serializers.DictField())
NO_CONTENT = {204: None}


def listing(*params):
    """``extend_schema_view`` pour la liste : déclare les paramètres lus par
    ``get_queryset``."""
    return extend_schema_view(
        list=extend_schema(parameters=list(params)))
